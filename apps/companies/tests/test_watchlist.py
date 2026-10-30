from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.companies.alerts import evaluate_price_alerts
from apps.companies.models import Company, CompanyPriceAlert, CompanyQuote, CompanyWatchlistEntry
from apps.delivery.models import DeliveryPreference
from apps.markets.streaming import FeedWriter
from apps.markets.upstox import Quote, save_quote

pytestmark = pytest.mark.django_db


@pytest.fixture
def member(django_user_model):
    user = django_user_model.objects.create_user("member", "member@example.com", "pw")
    DeliveryPreference.objects.create(user=user, email_verified_at=timezone.now())
    return user


def verified_user(django_user_model, username):
    user = django_user_model.objects.create_user(username, f"{username}@example.com", "pw")
    DeliveryPreference.objects.create(user=user, email_verified_at=timezone.now())
    return user


def test_watchlist_and_price_alerts_are_private_and_allow_multiple_thresholds(
    member, django_user_model
):
    company = Company.objects.create(
        name="Example", symbol="EXAMPLE", upstox_instrument_key="NSE_EQ|INE002A01018"
    )
    other_user = verified_user(django_user_model, "other")
    client = Client()
    client.force_login(member)
    other_client = Client()
    other_client.force_login(other_user)

    assert client.put(f"/api/app/watchlist/{company.pk}").json() == {"watchlisted": True}
    assert client.put(f"/api/app/watchlist/{company.pk}").json() == {"watchlisted": True}
    for threshold in ("105.50", "110.00"):
        response = client.post(
            f"/api/app/watchlist/{company.pk}/alerts",
            data={"above_price": threshold},
            content_type="application/json",
        )
        assert response.status_code == 201
    CompanyQuote.objects.create(
        company=company,
        instrument_key=company.upstox_instrument_key,
        as_of=timezone.now(),
        price=108.25,
        previous_close=105,
        mode="snapshot",
    )
    body = client.get("/api/app/watchlist").json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quote"]["price"] == 108.25
    assert [alert["above_price"] for alert in body["items"][0]["alerts"]] == [
        "110.00",
        "105.50",
    ]
    assert other_client.get("/api/app/watchlist").json() == {"items": []}

    alert_id = body["items"][0]["alerts"][0]["id"]
    assert other_client.delete(f"/api/app/watchlist/alerts/{alert_id}").status_code == 404
    assert client.delete(f"/api/app/watchlist/{company.pk}").json() == {"watchlisted": False}
    assert CompanyWatchlistEntry.objects.filter(user=member).count() == 0
    assert CompanyPriceAlert.objects.filter(pk=alert_id).count() == 0


def test_price_crossing_triggers_each_matching_alert_once_and_notifies_only_its_owner(
    member, django_user_model
):
    company = Company.objects.create(
        name="Example", symbol="EXAMPLE", upstox_instrument_key="NSE_EQ|INE002A01018"
    )
    entry = CompanyWatchlistEntry.objects.create(user=member, company=company)
    other_user = verified_user(django_user_model, "other")
    other_entry = CompanyWatchlistEntry.objects.create(user=other_user, company=company)
    alerts = [
        CompanyPriceAlert.objects.create(watchlist_entry=entry, above_price=threshold)
        for threshold in ("105.00", "110.00", "115.00")
    ]
    CompanyPriceAlert.objects.create(watchlist_entry=other_entry, above_price="105.00")
    stamp = timezone.now()
    CompanyQuote.objects.create(
        company=company,
        instrument_key="NSE_EQ|INE002A01018",
        as_of=stamp - timedelta(minutes=1),
        price=100,
        mode="stream",
    )
    writer = FeedWriter({company.upstox_instrument_key: company})
    writer.save(
        company.upstox_instrument_key,
        {
            "as_of": stamp.isoformat(),
            "ltp": 110,
            "previous_close": 100,
            "volume": 500,
        },
    )

    crossing = CompanyQuote.objects.get(company=company, as_of=stamp)
    assert crossing.mode == "stream"
    assert evaluate_price_alerts(crossing) == 0
    for alert in alerts:
        alert.refresh_from_db()
    assert [alert.is_active for alert in alerts] == [False, False, True]
    client = Client()
    client.force_login(member)
    other_client = Client()
    other_client.force_login(other_user)
    notifications = client.get("/api/app/watchlist/notifications").json()
    assert [item["id"] for item in notifications] == [alerts[1].pk, alerts[0].pk]
    assert all(Decimal(item["above_price"]) <= Decimal("110") for item in notifications)
    assert len(other_client.get("/api/app/watchlist/notifications").json()) == 1

    read = client.post(f"/api/app/watchlist/notifications/{alerts[0].pk}/read")
    assert read.json() == {"ok": True}
    assert [item["id"] for item in client.get("/api/app/watchlist/notifications").json()] == [
        alerts[1].pk
    ]


def test_snapshot_quote_creation_evaluates_price_alerts(member):
    company = Company.objects.create(
        name="Example", symbol="EXAMPLE", upstox_instrument_key="NSE_EQ|INE002A01018"
    )
    entry = CompanyWatchlistEntry.objects.create(user=member, company=company)
    alert = CompanyPriceAlert.objects.create(watchlist_entry=entry, above_price="105.00")
    stamp = timezone.now()
    CompanyQuote.objects.create(
        company=company,
        instrument_key=company.upstox_instrument_key,
        as_of=stamp - timedelta(minutes=1),
        price=100,
        mode="snapshot",
    )
    quote = Quote(
        instrument_token=company.upstox_instrument_key,
        timestamp=stamp,
        last_price=106,
        ohlc={"close": 100},
        volume=100,
    )

    assert save_quote(company, quote)
    assert not save_quote(company, quote)
    alert.refresh_from_db()
    assert not alert.is_active
    assert alert.triggered_price == 106


def test_watchlist_prices_and_alerts_require_markets_access(member):
    company = Company.objects.create(
        name="Example", symbol="EXAMPLE", upstox_instrument_key="NSE_EQ|INE002A01018"
    )
    entry = CompanyWatchlistEntry.objects.create(user=member, company=company)
    CompanyPriceAlert.objects.create(watchlist_entry=entry, above_price="105.00")
    CompanyQuote.objects.create(
        company=company,
        instrument_key=company.upstox_instrument_key,
        as_of=timezone.now(),
        price=110,
        mode="stream",
    )
    FeatureBlock.objects.create(user=member, feature="markets")
    client = Client()
    client.force_login(member)

    item = client.get("/api/app/watchlist").json()["items"][0]
    assert item["quote"] is None
    assert item["alerts"] == []
    assert (
        client.post(
            f"/api/app/watchlist/{company.pk}/alerts",
            data={"above_price": "120.00"},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert client.get("/api/app/watchlist/notifications").status_code == 403


def test_older_quote_does_not_trigger_alerts(member):
    company = Company.objects.create(name="Example", symbol="EXAMPLE")
    entry = CompanyWatchlistEntry.objects.create(user=member, company=company)
    alert = CompanyPriceAlert.objects.create(watchlist_entry=entry, above_price="105.00")
    stamp = timezone.now()
    CompanyQuote.objects.create(
        company=company,
        instrument_key="NSE_EQ|INE002A01018",
        as_of=stamp,
        price=110,
        mode="stream",
    )
    old_quote = CompanyQuote.objects.create(
        company=company,
        instrument_key="NSE_EQ|INE002A01018",
        as_of=stamp - timedelta(minutes=1),
        price=100,
        mode="stream",
    )

    assert evaluate_price_alerts(old_quote) == 0
    alert.refresh_from_db()
    assert alert.is_active
    assert alert.triggered_at is None
