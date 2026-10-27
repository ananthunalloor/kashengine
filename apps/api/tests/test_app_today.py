"""Today preview parity, feature redaction, and read-only browser access."""

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.access.features import KEYS
from apps.access.models import FeatureBlock
from apps.companies.models import Company, CompanyQuote
from apps.ipos.models import Ipo
from apps.markets.models import IndexQuote, Prediction
from apps.news.models import NewsArticle
from apps.reports.models import Report
from apps.siteconfig import conf
from apps.web.queries import dashboard_data

pytestmark = pytest.mark.django_db
URL = "/api/app/today"


def test_requires_browser_session_and_rejects_bearer(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    assert client.get("/dashboard/").status_code == 302
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401


@pytest.mark.parametrize("staff", [False, True])
def test_subscription_and_public_api_independence(client, member, expire, settings, staff):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    expire(member)
    member.is_staff = staff
    member.save(update_fields=["is_staff"])
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == (200 if staff else 403)
    preview = client.get("/dashboard/")
    assert preview.status_code == (200 if staff else 302)
    if not staff:
        assert response.json()["code"] == "subscription_required"
        assert preview.url == "/account/"


def test_empty_state_cache_and_legacy_page(client, member):
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == 200
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    body = response.json()
    assert body["markets"]["outlook"] is None
    assert body["markets"]["quotes"] == []
    assert body["markets"]["movers"] == {
        "as_of": None,
        "coverage": 0,
        "advancing": 0,
        "declining": 0,
        "unchanged": 0,
        "gainers": [],
        "losers": [],
    }
    assert body["markets"]["stats"]["accuracy"] == "–"
    assert body["news"]["good"] == body["news"]["bad"] == []
    assert body["ipos"]["open_now"] == body["ipos"]["upcoming"] == []
    assert body["report"] is None
    preview = client.get("/dashboard/")
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    assert "web/dashboard.html" not in [t.name for t in preview.templates]


def test_withheld_prediction_is_not_serialized_as_flat(client, member):
    Prediction.objects.create(
        target_date=timezone.localdate(),
        direction="withheld",
        confidence=0,
        score=0,
        inputs={"notes": ["No usable evidence."]},
    )
    client.force_login(member)
    response = client.get(URL)
    assert response.status_code == 200
    outlook = response.json()["markets"]["outlook"]
    assert outlook["direction"] == "withheld"
    assert outlook["notes"] == ["No usable evidence."]


@pytest.mark.parametrize("feature", ["markets", "news", "ipos", "reports"])
def test_blocked_sections_are_neither_read_nor_serialized(client, member, feature, data):
    FeatureBlock.objects.create(user=member, feature=feature)
    client.force_login(member)
    reader = {
        "markets": "market_stats",
        "news": "gather_news",
        "ipos": "dashboard_ipos",
        "reports": "Report.objects.first",
    }[feature]
    with patch(f"apps.api.app.today.{reader}", side_effect=AssertionError("Forbidden read")):
        response = client.get(URL)
    assert response.status_code == 200
    assert response.json()["report" if feature == "reports" else feature] is None


def test_no_features_is_an_empty_overview_not_an_error(client, member, data):
    FeatureBlock.objects.bulk_create(
        [FeatureBlock(user=member, feature=feature) for feature in KEYS]
    )
    client.force_login(member)
    body = client.get(URL).json()
    assert body == {
        "today": timezone.localdate(timezone=ZoneInfo("Asia/Kolkata")).isoformat(),
        "markets": None,
        "news": None,
        "ipos": None,
        "report": None,
        "stocks_watch": None,
    }
    assert client.get("/dashboard/").status_code == 200


def test_saved_outlook_actual_target_dates_cues_and_no_writes(client, member, data):
    prediction = Prediction.objects.get()
    prediction.direction = "down"
    prediction.confidence = 0.6
    prediction.news_score = 0
    prediction.global_score = None
    prediction.inputs = {
        "cues": [
            {
                "name": f"Instrument {index}",
                "change_pct": -index / 10,
                "as_of": "2026-10-06",
                "weight": 1,
                "signal": index / 10,
            }
            for index in range(7)
        ],
        "notes": ["<b>Saved, not recalculated</b>"],
    }
    prediction.save()
    before = {
        model: list(model.objects.values())
        for model in (Prediction, IndexQuote, NewsArticle, Ipo, Report)
    }
    client.force_login(member)
    body = client.get(URL).json()
    outlook = body["markets"]["outlook"]
    assert outlook["date"] == "2026-10-07"  # Never relabel an old outlook as today's.
    assert outlook["direction"] == "down"
    assert outlook["strength"] == "6.4/10"
    assert outlook["strength_label"] == "strong"
    assert outlook["news_score"] == "5.5/10"
    assert outlook["global_score"] == "–"
    assert outlook["notes"] == ["<b>Saved, not recalculated</b>"]
    assert [cue["name"] for cue in outlook["cues"]] == [
        f"Instrument {index}" for index in range(6, 1, -1)
    ]
    assert outlook["cues"][0] == {"name": "Instrument 6", "change": "−0.60%", "as_of": "2026-10-06"}
    assert body["report"] == {"date": "2026-10-07", "prediction": "up", "strength": "7.3/10"}
    assert "Report text" not in str(body)
    assert body["markets"]["quotes"][0]["change"] == "+0.40%"
    assert {model: list(model.objects.values()) for model in before} == before


def test_dashboard_movers_rank_latest_saved_company_quotes(client, member):
    as_of = datetime(2026, 10, 19, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    quote_data = [
        ("GAIN1", 110, 100),
        ("GAIN2", 105, 100),
        ("LOSS", 90, 100),
        ("FLAT", 100, 100),
        ("NOBASE", 110, None),
        ("OLD", 1000, 100),
    ]
    for symbol, price, previous_close in quote_data:
        company = Company.objects.create(
            name=f"{symbol} Company",
            symbol=symbol,
            upstox_instrument_key=f"NSE_EQ|{symbol}",
        )
        CompanyQuote.objects.create(
            company=company,
            instrument_key=company.upstox_instrument_key,
            as_of=as_of - timedelta(days=1) if symbol == "OLD" else as_of,
            price=price,
            previous_close=previous_close,
            mode="snapshot",
        )

    client.force_login(member)
    movers = client.get(URL).json()["markets"]["movers"]

    assert movers["coverage"] == 4
    assert movers["advancing"] == 2
    assert movers["declining"] == 1
    assert movers["unchanged"] == 1
    assert [row["symbol"] for row in movers["gainers"]] == ["GAIN1", "GAIN2"]
    assert [row["symbol"] for row in movers["losers"]] == ["LOSS"]
    assert movers["gainers"][0]["change_pct"] == pytest.approx(10)


def test_ist_date_news_window_ranking_and_ipo_group_parity(client, member, monkeypatch):
    now = datetime(2026, 10, 18, 20, 0, tzinfo=ZoneInfo("UTC"))
    monkeypatch.setattr("apps.api.app.today.timezone.now", lambda: now)
    today = date(2026, 10, 19)
    for index in range(6):
        for sign in (1, -1):
            NewsArticle.objects.create(
                title=f"{sign}: Story {index}",
                source="Mint",
                url=f"https://example.test/{sign}/{index}",
                sentiment_score=sign * (1 - index / 10),
                relevance=0.9,
                published_at=now - timedelta(hours=1),
                scored_at=now,
            )
    NewsArticle.objects.create(
        title="Outside the window",
        source="Mint",
        url="https://example.test/old",
        sentiment_score=1,
        relevance=1,
        published_at=now - timedelta(hours=37),
        scored_at=now,
    )
    for index in range(6):
        Ipo.objects.create(
            name=f"Good {index}",
            status="open",
            verdict="good",
            score=0.9,
            open_date=today,
            close_date=today + timedelta(days=2),
            gmp=-10,
            price_band_high=100,
        )
    Ipo.objects.create(
        name="Open only",
        status="open",
        open_date=today,
        close_date=today + timedelta(days=1),
        subscription_times=2,
    )
    Ipo.objects.create(
        name="Upcoming only",
        status="upcoming",
        open_date=today + timedelta(days=1),
    )
    expected = dashboard_data(now)
    client.force_login(member)
    body = client.get(URL).json()
    assert body["today"] == "2026-10-19"
    assert body["news"]["articles"] == expected["news"]["articles"] == 12
    assert body["news"]["positive"] == body["news"]["negative"] == 6
    for group in ("good", "bad"):
        assert [story["title"] for story in body["news"][group]] == [
            story["title"] for story in expected["news"][group]
        ]
        assert len(body["news"][group]) == 4
    for group in ("likely_good", "open_now", "upcoming"):
        assert [issue["name"] for issue in body["ipos"][group]] == [
            issue["name"] for issue in expected["ipos"][group]
        ]
        assert len(body["ipos"][group]) <= 4
    assert body["ipos"]["likely_good"][0]["gmp"] == "−10.0%"
    assert body["ipos"]["likely_good"][0]["price_band"] == "₹100"
    assert body["ipos"]["likely_good"][0]["score"] == "9.5/10"
