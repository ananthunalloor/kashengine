"""Stored provider ingestion, exact contracts and safe failure behavior."""

import signal
import ssl
from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.companies.models import Company, CompanyCandle, CompanyFundamentals, CompanyQuote
from apps.companies.outlook import save_outlook
from apps.ipos.models import Ipo
from apps.markets import streaming
from apps.markets.management.commands import stream_upstox
from apps.markets.streaming import FEED_RESPONSE, FeedWriter
from apps.markets.tasks import upstox_quotes, upstox_refresh
from apps.markets.trading import latest_completed_day
from apps.markets.upstox import sync_companies, sync_history, sync_ipos, sync_news, sync_quotes
from apps.markets.upstox_client import UpstoxClient, UpstoxError
from apps.news.models import NewsArticle
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db
KEY = "NSE_EQ|INE002A01018"


@pytest.fixture
def company(settings):
    settings.UPSTOX_ENABLED = True
    settings.UPSTOX_ACCESS_TOKEN = "fake-secret"
    conf.invalidate()
    yield Company.objects.create(name="Example", symbol="EXAMPLE", upstox_instrument_key=KEY)
    conf.invalidate()


def provider(handler):
    return UpstoxClient(httpx.Client(transport=httpx.MockTransport(handler)))


def response(data, **extra):
    return httpx.Response(200, json={"status": "success", "data": data, **extra})


def test_disabled_and_missing_token_do_not_call_provider(settings):
    settings.UPSTOX_ENABLED = False
    conf.invalidate()
    assert "skipped" in upstox_quotes()
    assert "skipped" in upstox_refresh()
    with pytest.raises(UpstoxError, match="disabled"):
        UpstoxClient()
    settings.UPSTOX_ENABLED = True
    settings.UPSTOX_ACCESS_TOKEN = ""
    conf.invalidate()
    with pytest.raises(UpstoxError, match="access token"):
        UpstoxClient()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_provider_failure_does_not_expose_tokens(company, status):
    client = provider(lambda request: httpx.Response(status, text="fake-secret"))
    with pytest.raises(UpstoxError, match=f"HTTP {status}") as exc:
        client.get("v2/news")
    assert "fake-secret" not in str(exc.value)


def test_news_pagination_company_linking_and_idempotency(company):
    visited = []

    def handler(request):
        assert request.headers["Authorization"] == "Bearer fake-secret"
        assert request.url.params["category"] == "instrument_keys"
        page = int(request.url.params["page_number"])
        visited.append(page)
        return response(
            {
                KEY: [
                    {
                        "heading": f"Story {page}",
                        "summary": "Summary",
                        "article_link": f"https://upstox.com/news/{page}/",
                        "published_time": 1776251261821,
                    }
                ]
            },
            metadata={"page": {"total_pages": 2}},
        )

    client = provider(handler)
    assert sync_news(client) == {"new": 2}
    article = NewsArticle.objects.first()
    assert article is not None
    article.sentiment_score = 0.7
    article.save()
    assert sync_news(client) == {"new": 0}
    article.refresh_from_db()
    assert article.sentiment_score == 0.7
    assert company.news_articles.count() == 2
    assert visited == [1, 2, 1, 2]


def test_missing_pagination_fails_explicitly(company):
    with pytest.raises(UpstoxError, match="pagination"):
        list(provider(lambda request: response([])).pages("v2/ipos", {}))


def test_quotes_deduplicate_and_failure_keeps_previous_data(company):
    payload = {
        "NSE_EQ:EXAMPLE": {
            "instrument_token": KEY,
            "timestamp": "2026-10-23T10:00:00+05:30",
            "last_price": 110,
            "volume": 1000,
            "ohlc": {"close": 100},
        },
    }
    client = provider(lambda request: response(payload))
    assert sync_quotes(client) == {"saved": 1, "failed": {}}
    assert sync_quotes(client)["saved"] == 0
    assert CompanyQuote.objects.get().previous_close == 100
    failed = provider(lambda request: httpx.Response(401))
    assert sync_quotes(failed)["failed"]
    assert CompanyQuote.objects.count() == 1
    company.refresh_from_db()
    assert company.upstox_errors["quotes"]
    assert sync_quotes(client)["failed"] == {}
    company.refresh_from_db()
    assert not company.upstox_errors


def test_history_incremental_backfill_skips_partial_today(company, monkeypatch):
    monkeypatch.setattr("apps.markets.upstox.today_ist", lambda: date(2026, 10, 23))
    monkeypatch.setattr("apps.markets.upstox.latest_completed_day", lambda: date(2026, 10, 22))
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return response(
            {
                "candles": [
                    ["2026-10-22T00:00:00+05:30", 99, 102, 98, 100, 1000, 0],
                    ["2026-10-23T00:00:00+05:30", 100, 112, 98, 110, 500, 0],
                ]
            }
        )

    client = provider(handler)
    assert sync_history(company, client) == 1
    assert sync_history(company, client) == 1
    assert CompanyCandle.objects.count() == 1
    assert paths[-1].endswith("/2026-10-23/2026-10-22")


def test_fundamentals_refresh_cache_and_retained_snapshot(company):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if "historical-candle" in request.url.path:
            return response({"candles": []})
        if request.url.path.endswith("/profile"):
            return response({"company_profile": "Business summary", "sector": "Energy"})
        return response([])

    client = provider(handler)
    assert sync_companies(client)["fundamentals"] == 1
    assert CompanyFundamentals.objects.count() == 1
    assert sync_companies(client)["fundamentals"] == 0
    assert sum(path.endswith("/profile") for path in paths) == 1
    CompanyFundamentals.objects.update(fetched_at=timezone.now() - timedelta(days=8))
    failing = provider(lambda request: httpx.Response(403))
    result = sync_companies(failing)
    assert len(result["failed"]) == 2
    assert CompanyFundamentals.objects.count() == 1
    assert (
        CompanyFundamentals.objects.get().data["profile"]["company_profile"] == "Business summary"
    )


def test_ipo_all_stages_detail_mapping_and_saved_payload(company):
    statuses = []

    def handler(request):
        if request.url.path == "/v2/ipos":
            statuses.append(request.url.params["status"])
            return response([{"id": "example-ipo"}], meta_data={"page": {"total_pages": 1}})
        return response(
            {
                "id": "example-ipo",
                "name": "Example IPO",
                "symbol": "EXAMPLE",
                "isin": "INE002A01018",
                "issue_type": "regular",
                "minimum_price": 100,
                "maximum_price": 110,
                "lot_size": 50,
                "bidding_start_date": "2026-10-26",
                "bidding_end_date": "2026-10-28",
                "issue_size": 250,
                "total_subscription": "1.25",
                "timeline": {"listing_date": "2026-11-02"},
                "listing_price": None,
            }
        )

    sync_ipos(provider(handler))
    assert statuses == ["upcoming", "open", "closed", "listed"]
    assert Ipo.objects.count() == 1
    ipo = Ipo.objects.get()
    assert ipo.upstox_id == "example-ipo"
    assert ipo.subscription_times == 1.25
    assert ipo.lot_size == 50
    assert ipo.listing_date == date(2026, 11, 2)
    assert ipo.upstox_data["issue_size"] == 250


def test_ipo_invalid_detail_is_skipped_without_aborting_refresh(company, caplog):
    def handler(request):
        if request.url.path == "/v2/ipos":
            return response(
                [{"id": "invalid-ipo"}, {"id": "valid-ipo"}],
                meta_data={"page": {"total_pages": 1}},
            )
        if request.url.path.endswith("/invalid-ipo"):
            return response({"id": "invalid-ipo", "name": "Sensitive payload value"})
        return response(
            {
                "id": "valid-ipo",
                "name": "Valid IPO",
                "issue_type": "regular",
            }
        )

    counts = sync_ipos(provider(handler))

    assert counts["skipped"] == 1
    assert Ipo.objects.count() == 1
    assert Ipo.objects.get().name == "Valid IPO"
    assert "issue_type" in caplog.text
    assert "Sensitive payload value" not in caplog.text


def test_experimental_outlook_threshold_evidence_and_insufficient_data(company, monkeypatch):
    monkeypatch.setattr("apps.companies.outlook.latest_completed_day", lambda: date(2026, 10, 22))
    assert save_outlook(company) is None
    for offset in range(21):
        CompanyCandle.objects.create(
            company=company,
            instrument_key=KEY,
            day=date(2026, 10, 22) - timedelta(days=offset),
            open=110 - offset / 2,
            high=111,
            low=99,
            close=110 - offset / 2,
            volume=100,
        )
    outlook = save_outlook(company)
    assert outlook is not None
    assert outlook.direction == "up"
    assert outlook.score == pytest.approx(1)
    assert outlook.news_score is None
    assert outlook.inputs["return_20_sessions_pct"] == pytest.approx(10)
    assert outlook.target_date == date(2026, 10, 23)
    repeated = save_outlook(company)
    assert repeated is not None
    assert repeated.pk == outlook.pk
    article = NewsArticle.objects.create(
        source="Test",
        title="Bad",
        url="https://example.com/a",
        published_at=timezone.now(),
        sentiment_score=-1,
        relevance=1,
    )
    article.companies.add(company)
    updated = save_outlook(company)
    assert updated is not None
    assert updated.score == pytest.approx(0.4)
    assert updated.inputs["news"][0]["id"] == article.pk


def test_stream_decodes_official_protobuf_and_throttles(company, monkeypatch):
    clock = Mock(return_value=100)
    monkeypatch.setattr("apps.markets.streaming.time.monotonic", clock)
    writer = FeedWriter({KEY: company})
    socket = Mock()
    packet = FEED_RESPONSE()
    packet.feeds[KEY].ltpc.ltp = 110
    packet.feeds[KEY].ltpc.ltt = int(datetime(2026, 10, 23, 5, tzinfo=UTC).timestamp() * 1000)
    packet.feeds[KEY].ltpc.cp = 100
    writer.on_message(socket, packet.SerializeToString())
    assert CompanyQuote.objects.get().mode == "stream"
    packet.feeds[KEY].ltpc.ltt += 1000
    writer.on_message(socket, packet.SerializeToString())
    assert CompanyQuote.objects.count() == 1
    clock.return_value = 106
    writer.on_message(socket, packet.SerializeToString())
    assert CompanyQuote.objects.count() == 2
    writer.on_message(socket, b"malformed")
    assert writer.invalid
    socket.close.assert_called_once()


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        ("2026-10-23T10:09:59+00:00", date(2026, 10, 22)),
        ("2026-10-23T10:10:00+00:00", date(2026, 10, 23)),
        ("2026-10-24T12:00:00+00:00", date(2026, 10, 23)),
    ],
)
def test_completed_session_respects_close_buffer(company, settings, stamp, expected):
    settings.MARKET_CLOSE_TIME = "15:30"
    settings.MARKET_FINAL_BUFFER_MINUTES = 10
    conf.invalidate()
    assert latest_completed_day(datetime.fromisoformat(stamp)) == expected


@pytest.mark.parametrize(
    ("closing", "direction"),
    [(101.5, "flat"), (98.5, "flat"), (101.6, "up"), (98.4, "down")],
)
def test_outlook_flat_threshold_and_after_close_target(company, monkeypatch, closing, direction):
    monkeypatch.setattr("apps.companies.outlook.latest_completed_day", lambda: date(2026, 10, 23))
    for offset in range(21):
        price = closing if offset == 0 else 100
        CompanyCandle.objects.create(
            company=company,
            instrument_key=KEY,
            day=date(2026, 10, 23) - timedelta(days=offset),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=100,
        )
    outlook = save_outlook(company)
    assert outlook is not None
    assert outlook.direction == direction
    assert outlook.target_date == date(2026, 10, 26)
    monkeypatch.setattr("apps.companies.outlook.latest_completed_day", lambda: date(2026, 10, 26))
    assert save_outlook(company) is None


def test_snapshot_does_not_hide_newer_stream_observation(company):
    CompanyQuote.objects.create(
        company=company,
        instrument_key=KEY,
        as_of=datetime(2026, 10, 23, 5, 1, tzinfo=UTC),
        price=112,
        previous_close=100,
        volume=None,
        mode="stream",
    )
    client = provider(
        lambda request: response(
            {
                "NSE_EQ:EXAMPLE": {
                    "instrument_token": KEY,
                    "timestamp": "2026-10-23T10:30:00+05:30",
                    "last_price": 110,
                    "volume": 1000,
                    "ohlc": {"close": 100},
                }
            }
        )
    )
    sync_quotes(client)
    latest = company.quotes.first()
    assert latest is not None
    assert latest.price == 112


@pytest.mark.parametrize("uri", ["ws://feed.upstox.com/path", "wss://example.com/path"])
def test_stream_authorization_rejects_non_tls_or_untrusted_hosts(company, monkeypatch, uri):
    client = provider(lambda request: response({"authorized_redirect_uri": uri}))
    monkeypatch.setattr(streaming, "UpstoxClient", lambda: client)
    with pytest.raises(UpstoxError, match="invalid streaming endpoint"):
        streaming.authorized_uri()


def test_stream_worker_requires_tls_verification_and_restores_signals(company, monkeypatch):
    socket = Mock()
    previous = signal.getsignal(signal.SIGTERM)

    def shutdown(**kwargs):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        handler(signal.SIGTERM, None)

    socket.run_forever.side_effect = shutdown
    monkeypatch.setattr(stream_upstox, "authorized_uri", lambda: "wss://feed.upstox.com/path")
    monkeypatch.setattr(stream_upstox.websocket, "WebSocketApp", lambda *args, **kwargs: socket)
    call_command("stream_upstox")
    assert socket.run_forever.call_args.kwargs["sslopt"] == {
        "cert_reqs": ssl.CERT_REQUIRED,
        "check_hostname": True,
    }
    assert signal.getsignal(signal.SIGTERM) is previous
