from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps.api import tokens
from apps.companies.models import Company
from apps.delivery.models import DeliveryLog
from apps.ipos.models import Ipo
from apps.markets.models import IndexQuote, Instrument, Prediction
from apps.news.models import NewsArticle
from apps.reports.models import Report

PASSWORD = "pw-api-test-1"


@pytest.fixture(autouse=True)
def api_test_setup(settings):
    """Fast password hashing, and an empty cache (the rate-limit counters live there)."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def member(django_user_model):
    return django_user_model.objects.create_user("member", "member@example.com", PASSWORD)


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        "staff", "staff@example.com", PASSWORD, is_staff=True
    )


@pytest.fixture
def make_token():
    """Return a function that makes a token for a user and gives back (row, raw text)."""

    def _make(user, name="test"):
        return tokens.issue(user, name)

    return _make


@pytest.fixture
def auth():
    """Return the headers for a bearer token."""

    def _auth(raw: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {raw}"}

    return _auth


@pytest.fixture
def api(member, make_token, auth):
    """A client function that calls the API as `member` with a bearer token."""
    _row, raw = make_token(member)
    client = Client()

    def get(path: str, **extra):
        return client.get(path, headers=auth(raw), **extra)

    return get


@pytest.fixture
def staff_api(staff, make_token, auth):
    _row, raw = make_token(staff)
    client = Client()

    def get(path: str, **extra):
        return client.get(path, headers=auth(raw), **extra)

    return get


@pytest.fixture
def data(db):
    """One row of each kind of data."""
    now = timezone.now()
    today = date(2026, 10, 7)
    company = Company.objects.create(
        name="Tata Motors", symbol="TATAMOTORS", sector="Auto", aliases=["Tata Motors Ltd"]
    )
    article = NewsArticle.objects.create(
        source="Mint",
        title="Auto sales jump in September",
        url="https://example.com/a1",
        summary="Sales rose.",
        published_at=now,
        sentiment_score=0.6,
        sentiment_reason="Strong sales.",
        relevance=0.8,
        scored_at=now,
    )
    article.companies.add(company)
    NewsArticle.objects.create(
        source="Hindu", title="Unscored story", url="https://example.com/a2", published_at=now
    )
    report = Report.objects.create(
        date=today, text="Report text", prediction="up", confidence=0.7, data={"k": 1}
    )
    ipo = Ipo.objects.create(
        name="Acme Ltd",
        company=company,
        category="mainboard",
        status="open",
        open_date=today,
        price_band_low="90",
        price_band_high="100",
        gmp="20",
        score=0.4,
        verdict="good",
        score_inputs={
            "signals": [{"name": "gmp", "value": 20.0, "signal": 0.5, "strength": 1.0}],
            "notes": ["No subscription number."],
        },
    )
    Ipo.objects.create(name="Old Ltd", status="listed", open_date=today - timedelta(days=60))
    Prediction.objects.create(
        target_date=today,
        direction="up",
        confidence=0.7,
        score=0.4,
        news_score=0.3,
        global_score=0.5,
        news_articles=12,
        inputs={
            "cues": [
                {
                    "symbol": "^GSPC",
                    "name": "S&P 500",
                    "change_pct": 1.2,
                    "as_of": "2026-10-06",
                    "weight": 0.5,
                    "signal": 0.8,
                }
            ],
            "notes": ["One cue is missing."],
        },
        actual_direction="up",
        actual_change_pct=0.5,
        correct=True,
        evaluated_at=now,
    )
    symbol = Instrument.objects.filter(kind="target").first()
    assert symbol is not None
    IndexQuote.objects.create(symbol=symbol.symbol, day=today, close=25000.5, change_pct=0.4)
    DeliveryLog.objects.create(
        report=report,
        channel="telegram",
        status="failed",
        recipient="1234567890",
        error="Chat not found",
    )
    return {"company": company, "article": article, "report": report, "ipo": ipo}
