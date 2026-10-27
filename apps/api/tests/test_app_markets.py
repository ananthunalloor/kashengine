"""Markets preview parity, formatting, saved-result semantics, and access rules."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.companies.models import Company
from apps.markets.evaluation import accuracy_stats
from apps.markets.models import IndexQuote, Instrument, MarketInstrument, Prediction
from apps.siteconfig import conf
from apps.web.queries import latest_quotes, prediction_history
from apps.web.templatetags.web_extras import percent

pytestmark = pytest.mark.django_db
URL = "/api/app/markets"
INSTRUMENTS_URL = "/api/app/markets/instruments"


def test_session_feature_and_bearer_rejection(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    assert client.get("/markets/").status_code == 302
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="markets")
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "feature_not_available"
    assert client.get("/markets/").status_code == 403


@pytest.mark.parametrize("staff", [False, True])
def test_subscription_staff_and_public_api_independence(client, member, expire, settings, staff):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    member.is_staff = staff
    member.save(update_fields=["is_staff"])
    expire(member)
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == (200 if staff else 403)
    preview = client.get("/markets/")
    assert preview.status_code == (200 if staff else 302)
    if not staff:
        assert preview.url == "/account/"
    if not staff:
        assert client.get(URL).json()["code"] == "subscription_required"


def test_empty_state_private_cache_and_original_page(client, member):
    Prediction.objects.all().delete()
    IndexQuote.objects.all().delete()
    client.force_login(member)
    response = client.get(URL)
    body = response.json()
    assert response.status_code == 200
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    assert body["history"] == body["quotes"] == []
    assert body["stats"]["total"] == body["stats"]["pending"] == 0
    assert body["stats"]["accuracy"] == body["stats"]["baseline_accuracy"] == "–"
    assert body["stats"]["baseline_direction"] is None
    assert not body["stats"]["enough_results"]
    preview = client.get("/markets/")
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    assert "web/markets.html" not in [t.name for t in preview.templates]


def test_exchange_instrument_catalog_search_filters_and_pagination(client, member, settings):
    settings.WEB_PAGE_SIZE = 1
    conf.invalidate()
    company = Company.objects.create(name="Reliance Industries", symbol="RELIANCE")
    MarketInstrument.objects.create(
        instrument_key="NSE_EQ|INE002A01018",
        exchange="NSE",
        segment="NSE_EQ",
        trading_symbol="RELIANCE",
        name=company.name,
        instrument_type="EQ",
        isin="INE002A01018",
        company=company,
    )
    MarketInstrument.objects.create(
        instrument_key="NSE_FO|RELIANCE26JUNFUT",
        exchange="NSE",
        segment="NSE_FO",
        trading_symbol="RELIANCE26JUNFUT",
        name=company.name,
        instrument_type="FUTSTK",
        underlying_symbol="RELIANCE",
        company=company,
    )
    MarketInstrument.objects.create(
        instrument_key="BSE_EQ|INE002A01018",
        exchange="BSE",
        segment="BSE_EQ",
        trading_symbol="500325",
        name=company.name,
        instrument_type="EQ",
        company=company,
    )
    client.force_login(member)

    first_page = client.get(INSTRUMENTS_URL, {"exchange": "NSE"}).json()
    second_page = client.get(INSTRUMENTS_URL, {"exchange": "NSE", "page": 2}).json()
    contract = client.get(INSTRUMENTS_URL, {"q": "26JUN", "instrument_type": "FUTSTK"}).json()

    assert first_page["total"] == 2
    assert first_page["pages"] == 2
    assert first_page["items"][0]["trading_symbol"] == "RELIANCE"
    assert first_page["segments"] == ["NSE_EQ", "NSE_FO"]
    assert second_page["items"][0]["trading_symbol"] == "RELIANCE26JUNFUT"
    assert second_page["items"][0]["company_id"] == company.pk
    assert contract["total"] == 1
    assert contract["items"][0]["instrument_type"] == "FUTSTK"


def test_results_formatting_statistics_and_read_only(client, member):
    Prediction.objects.all().delete()
    stamp = timezone.now()
    for offset, (correct, evaluated, actual, change) in enumerate(
        [
            (True, stamp, "up", 1.25),
            (False, stamp, "flat", 0),
            (None, stamp, "", None),
            (None, None, "", None),
        ]
    ):
        Prediction.objects.create(
            target_date=date(2026, 10, 16) - timedelta(days=offset),
            direction="down" if correct is False else "up",
            confidence=0.6 if correct is True else 0,
            score=0,
            correct=correct,
            actual_direction=actual,
            actual_change_pct=change,
            evaluated_at=evaluated,
            inputs={"notes": ["Saved, not recomputed"]},
        )
    before = list(Prediction.objects.values())
    client.force_login(member)
    body = client.get(URL).json()
    expected = accuracy_stats()
    stats = body["stats"]
    for field in ("total", "correct", "pending", "recent", "high_confidence", "enough_results"):
        assert stats[field] == expected[field]
    assert stats["accuracy"] == percent(expected["accuracy"]) == "50%"
    assert stats["baseline_accuracy"] == percent(expected["baseline_accuracy"])
    assert stats["baseline_direction"] == expected["baseline_direction"] == "up"
    assert [row["result"] for row in body["history"]] == ["Right", "Wrong", "No session", "Waiting"]
    assert [row["change"] for row in body["history"]] == ["+1.25%", "0.00%", "–", "–"]
    assert [row["strength"] for row in body["history"]] == ["6.4/10", "1.0/10", "1.0/10", "1.0/10"]
    assert list(Prediction.objects.values()) == before


def test_newest_thirty_and_enough_results_threshold(client, member):
    Prediction.objects.all().delete()
    for offset in range(31):
        Prediction.objects.create(
            target_date=date(2026, 10, 16) - timedelta(days=offset),
            direction="flat",
            confidence=1,
            score=0,
            correct=True,
            actual_direction="flat",
            actual_change_pct=-0.01,
            evaluated_at=timezone.now(),
        )
    client.force_login(member)
    body = client.get(URL).json()
    assert len(body["history"]) == 30
    assert [row["date"] for row in body["history"]] == [
        prediction.target_date.isoformat() for prediction in prediction_history()
    ]
    assert body["history"][0]["change"] == "−0.01%"
    assert body["stats"]["total"] == 31
    assert body["stats"]["enough_results"]
    oldest = Prediction.objects.last()
    assert oldest is not None
    oldest.delete()
    assert client.get(URL).json()["stats"]["enough_results"]
    oldest = Prediction.objects.last()
    assert oldest is not None
    oldest.delete()
    assert not client.get(URL).json()["stats"]["enough_results"]


def test_latest_enabled_quotes_preserve_dates_zero_and_missing_values(client, member):
    Instrument.objects.all().delete()
    IndexQuote.objects.all().delete()
    for symbol in ("ZERO", "MISSING", "NEGATIVE", "DISABLED", "NO-DATA"):
        Instrument.objects.create(symbol=symbol, name=symbol, enabled=symbol != "DISABLED")
    for symbol, close, change in (
        ("ZERO", 0, 0),
        ("MISSING", 100.125, None),
        ("NEGATIVE", 99.5, -1.25),
        ("DISABLED", 10, 1),
        ("UNCONFIGURED", 10, 1),
    ):
        IndexQuote.objects.create(
            symbol=symbol, day=date(2026, 10, 16), close=close, change_pct=change
        )
    IndexQuote.objects.create(symbol="ZERO", day=date(2026, 10, 15), close=12, change_pct=2)
    before = list(IndexQuote.objects.values())
    client.force_login(member)
    body = client.get(URL).json()
    assert [row["name"] for row in body["quotes"]] == [row["name"] for row in latest_quotes()]
    assert [row["close"] for row in body["quotes"]] == ["0.00", "100.13", "99.50"]
    assert [row["change"] for row in body["quotes"]] == ["0.00%", "–", "−1.25%"]
    assert all(row["day"] == "2026-10-16" for row in body["quotes"])
    assert list(IndexQuote.objects.values()) == before
