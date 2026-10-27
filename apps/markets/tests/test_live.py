"""Live Upstox quotes: full-mode decoding, bounded publishing and the browser WebSocket."""

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator
from channels.testing.websocket import WebsocketCommunicator
from django.conf import settings
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.companies.models import Company, CompanyQuote
from apps.delivery.models import DeliveryPreference
from apps.markets import consumers, live
from apps.markets.models import LiveSnapshot
from apps.markets.streaming import FEED_RESPONSE, FeedWriter
from config.asgi import application

pytestmark = pytest.mark.django_db(transaction=True)
KEY = "NSE_EQ|INE002A01018"
NIFTY = "NSE_INDEX|Nifty 50"
STAMP = int(datetime(2026, 10, 23, 5, tzinfo=UTC).timestamp() * 1000)


@pytest.fixture
def company():
    return Company.objects.create(name="Example", symbol="EXAMPLE", upstox_instrument_key=KEY)


@pytest.fixture
def member(django_user_model):
    user = django_user_model.objects.create_user("member", "member@example.com", "pw-123456789")
    DeliveryPreference.objects.create(user=user, email_verified_at=timezone.now())
    return user


def full_packet():
    packet = FEED_RESPONSE()
    market = packet.feeds[KEY].fullFeed.marketFF
    market.ltpc.ltp = 110
    market.ltpc.ltt = STAMP
    market.ltpc.cp = 100
    market.vtt = 5000
    market.atp = 108.5
    market.tbq = 1200
    market.tsq = 800
    bar = market.marketOHLC.ohlc.add()
    bar.interval, bar.open, bar.high, bar.low = "1d", 101, 112, 99
    minute = market.marketOHLC.ohlc.add()
    minute.interval, minute.open = "I1", 1
    for level in range(6):
        quote = market.marketLevel.bidAskQuote.add()
        quote.bidP, quote.bidQ, quote.askP, quote.askQ = 109.9 - level, 10, 110.1 + level, 20
    index = packet.feeds[NIFTY].fullFeed.indexFF
    index.ltpc.ltp = 25000
    index.ltpc.ltt = STAMP
    index.ltpc.cp = 24750
    return packet


def test_full_feed_is_normalized_published_and_saved_without_signals(company, monkeypatch):
    published = Mock()
    monkeypatch.setattr("apps.api.live.publish", published)
    writer = FeedWriter({KEY: company}, [NIFTY])
    writer.on_message(Mock(), full_packet().SerializeToString())
    status = FEED_RESPONSE()
    status.type = 2  # market_info
    status.marketInfo.segmentStatus["NSE_EQ"] = 2
    writer.on_message(Mock(), status.SerializeToString())

    layer = get_channel_layer()
    receiver = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(live.INDEX_GROUP, receiver)
    company_receiver = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(live.company_group(company.pk), company_receiver)
    writer.publish()

    equity = LiveSnapshot.objects.get(key=KEY).payload
    assert equity["company_id"] == company.pk
    assert equity["ltp"] == 110
    assert equity["change"] == 10
    assert equity["change_pct"] == pytest.approx(10)
    assert (equity["open"], equity["high"], equity["low"]) == (101, 112, 99)
    assert equity["volume"] == 5000
    assert equity["average_price"] == pytest.approx(108.5)
    assert len(equity["depth"]) == live.DEPTH_LEVELS
    assert equity["depth"][0] == {
        "bid_price": 109.9,
        "bid_qty": 10,
        "ask_price": 110.1,
        "ask_qty": 20,
    }
    index = LiveSnapshot.objects.get(key=NIFTY).payload
    assert index["name"] == "Nifty 50"
    assert index["kind"] == "index"
    assert "depth" not in index
    assert LiveSnapshot.objects.get(key=live.STATUS_KEY).payload["segments"] == {
        "NSE_EQ": "NORMAL_OPEN"
    }
    assert CompanyQuote.objects.get().volume == 5000

    messages = [async_to_sync(layer.receive)(receiver) for _ in range(2)]
    assert {message["type"] for message in messages} == {"market.status", "quote.update"}
    company_message = async_to_sync(layer.receive)(company_receiver)
    assert company_message["quotes"][0]["key"] == KEY
    published.assert_not_called()
    writer.publish()
    assert LiveSnapshot.objects.count() == 3


def test_broadcast_failure_does_not_stop_the_stream(company, monkeypatch, caplog):
    monkeypatch.setattr(live, "broadcast", Mock(side_effect=ConnectionError("redis down")))
    writer = FeedWriter({KEY: company})
    writer.on_message(Mock(), full_packet().SerializeToString())
    writer.publish()
    writer.on_message(Mock(), full_packet().SerializeToString())
    writer.publish()
    assert LiveSnapshot.objects.filter(key=KEY).exists()
    assert caplog.text.count("Could not broadcast") == 1
    assert not writer.invalid


def test_publisher_thread_reuses_one_event_loop(company, monkeypatch):
    """The Redis layer pools connections per loop; a new loop each second means a new connection."""
    loops = []
    monkeypatch.setattr(live, "broadcast", lambda payloads, loop=None: loops.append(loop))
    # Django keeps in-memory SQLite test connections open, so the thread must not use the DB.
    monkeypatch.setattr(live, "store", Mock())
    monkeypatch.setattr("apps.markets.streaming.PUBLISH_INTERVAL", 0.01)
    writer = FeedWriter({KEY: company})
    writer.start()
    try:
        for _ in range(3):
            writer.on_message(Mock(), full_packet().SerializeToString())
            deadline = time.monotonic() + 5
            count = len(loops)
            while len(loops) == count and time.monotonic() < deadline:
                time.sleep(0.01)
    finally:
        writer.stop()
    assert len(loops) >= 3
    assert all(isinstance(loop, asyncio.AbstractEventLoop) for loop in loops)
    assert len({id(loop) for loop in loops}) == 1
    assert loops[0].is_closed()


def test_unknown_or_empty_feeds_are_ignored(company):
    writer = FeedWriter({KEY: company})
    packet = FEED_RESPONSE()
    packet.feeds["NSE_EQ|OTHER"].ltpc.ltp = 5
    packet.feeds["NSE_EQ|OTHER"].ltpc.ltt = STAMP
    packet.feeds[KEY].fullFeed.marketFF.vtt = 10
    writer.on_message(Mock(), packet.SerializeToString())
    assert writer.pending == {}
    assert not writer.invalid


def connect(user=None, origin=b"http://localhost", app=application):
    headers = [(b"origin", origin)]
    if user is not None:
        from django.test import Client  # noqa: PLC0415

        client = Client()
        client.force_login(user)
        cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
        headers.append((b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode()))
    return WebsocketCommunicator(app, "/ws/live/quotes/", headers=headers)


async def closed_code(communicator):
    connected, _ = await communicator.connect()
    assert connected
    message = await communicator.receive_output()
    await communicator.wait()
    return message.get("code")


def test_socket_requires_session_and_markets_feature(member):
    assert async_to_sync(closed_code)(connect()) == consumers.UNAUTHENTICATED
    FeatureBlock.objects.create(user=member, feature="markets")
    assert async_to_sync(closed_code)(connect(member)) == consumers.FORBIDDEN


def test_socket_rejects_foreign_origin(member, settings):
    settings.ALLOWED_HOSTS = ["localhost"]
    validator = application.application_mapping["websocket"]
    assert isinstance(validator, OriginValidator)
    app = AllowedHostsOriginValidator(validator.application)
    assert async_to_sync(connect(member, b"http://localhost", app).connect)()[0] is True
    communicator = connect(member, b"https://evil.example", app)

    async def run():
        connected, _ = await communicator.connect()
        return connected

    assert async_to_sync(run)() is False


def test_socket_sends_snapshots_and_relays_subscribed_quotes(member, company):
    other = Company.objects.create(name="Other", symbol="OTHER", upstox_instrument_key="NSE_EQ|X")
    unmapped = Company.objects.create(name="Unmapped", symbol="NONE")
    live.store(
        [
            {"key": NIFTY, "kind": "index", "company_id": None, "ltp": 25000},
            {"key": KEY, "kind": "equity", "company_id": company.pk, "ltp": 110},
            {"key": live.STATUS_KEY, "kind": "status", "segments": {"NSE_EQ": "NORMAL_OPEN"}},
        ]
    )

    communicator = connect(member)

    async def run():
        connected, _ = await communicator.connect()
        assert connected
        first = await communicator.receive_json_from()
        assert first["type"] == "snapshot"
        assert [quote["key"] for quote in first["quotes"]] == [NIFTY]
        assert first["status"]["segments"] == {"NSE_EQ": "NORMAL_OPEN"}

        await communicator.send_json_to({"type": "subscribe", "companies": ["1"]})
        assert (await communicator.receive_json_from())["type"] == "error"
        await communicator.send_to(text_data="not json")
        assert (await communicator.receive_json_from())["type"] == "error"
        too_many = list(range(1, consumers.MAX_COMPANIES + 2))
        await communicator.send_json_to({"type": "subscribe", "companies": too_many})
        assert (await communicator.receive_json_from())["type"] == "error"

        await communicator.send_json_to(
            {"type": "subscribe", "companies": [company.pk, unmapped.pk]}
        )
        snapshot = await communicator.receive_json_from()
        assert [quote["key"] for quote in snapshot["quotes"]] == [KEY]
        assert "status" not in snapshot

        layer = get_channel_layer()
        quote = {"key": KEY, "company_id": company.pk, "ltp": 111}
        await layer.group_send(
            live.company_group(company.pk), {"type": "quote.update", "quotes": [quote]}
        )
        assert await communicator.receive_json_from() == {"type": "quotes", "quotes": [quote]}
        await layer.group_send(
            live.company_group(other.pk), {"type": "quote.update", "quotes": [quote]}
        )
        assert await communicator.receive_nothing(0.2)
        await layer.group_send(live.INDEX_GROUP, {"type": "market.status", "status": {"a": 1}})
        assert await communicator.receive_json_from() == {"type": "status", "status": {"a": 1}}

        await communicator.send_json_to({"type": "subscribe", "companies": []})
        await communicator.receive_json_from()
        await layer.group_send(
            live.company_group(company.pk), {"type": "quote.update", "quotes": [quote]}
        )
        assert await communicator.receive_nothing(0.2)
        await communicator.disconnect()

    async_to_sync(run)()


def test_socket_closes_after_sign_out(member, monkeypatch):
    monkeypatch.setattr(consumers, "REVALIDATE_SECONDS", 0.05)

    communicator = connect(member)

    async def run():
        await communicator.connect()
        await communicator.receive_json_from()
        from channels.db import database_sync_to_async  # noqa: PLC0415
        from django.contrib.sessions.models import Session  # noqa: PLC0415

        await database_sync_to_async(lambda: Session.objects.all().delete())()
        message = await asyncio.wait_for(communicator.receive_output(), 2)
        assert message == {"type": "websocket.close", "code": consumers.UNAUTHENTICATED}

    async_to_sync(run)()
