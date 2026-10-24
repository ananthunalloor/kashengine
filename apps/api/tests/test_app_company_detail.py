"""Company detail and market pages are database-only and preserve feature boundaries."""

from datetime import UTC, date, datetime

import pytest

from apps.access.models import FeatureBlock
from apps.companies.models import Company, CompanyFundamentals, CompanyOutlook, CompanyQuote
from apps.ipos.models import Ipo
from apps.news.models import NewsArticle

pytestmark = pytest.mark.django_db
KEY = "NSE_EQ|INE002A01018"


@pytest.fixture
def company():
    company = Company.objects.create(name="Example", symbol="EXAMPLE", upstox_instrument_key=KEY)
    CompanyFundamentals.objects.create(
        company=company,
        instrument_key=KEY,
        data={"profile": {"company_profile": "<b>Business summary</b>"}, "key-ratios": []},
    )
    CompanyQuote.objects.create(
        company=company,
        instrument_key=KEY,
        as_of=datetime(2026, 10, 23, 5, tzinfo=UTC),
        price=110,
        previous_close=100,
        volume=1000,
        mode="snapshot",
    )
    CompanyOutlook.objects.create(
        company=company,
        target_date=date(2026, 10, 26),
        direction="up",
        score=0.5,
        momentum_score=0.6,
        news_score=0.3,
        inputs={"instrument_key": KEY, "method": "test"},
    )
    story = NewsArticle.objects.create(
        title="News",
        source="Test",
        url="https://example.com/news",
        sentiment_score=0.3,
        relevance=0.7,
    )
    story.companies.add(company)
    Ipo.objects.create(name="Example IPO", company=company, score=0.4, score_inputs={"test": 0.4})
    return company


def test_detail_saved_only_and_complete_scores(client, member, company, monkeypatch):
    def forbid(*args, **kwargs):
        pytest.fail("Company pages must not contact a provider.")

    monkeypatch.setattr("httpx.Client.request", forbid)
    client.force_login(member)
    before = CompanyOutlook.objects.count()
    response = client.get(f"/api/app/companies/{company.pk}")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "<b>Business summary</b>"
    assert body["fundamentals_source"] == "Upstox"
    assert body["quote"]["change_pct"] == pytest.approx(10)
    assert body["outlook"]["score"] == 0.5
    assert body["news"][0]["sentiment_score"] == 0.3
    assert body["ipos"][0]["score_inputs"] == {"test": 0.4}
    assert CompanyOutlook.objects.count() == before
    assert "no-store" in response["Cache-Control"]
    assert client.get(f"/companies/{company.pk}/").status_code == 200
    assert client.get("/companies/999999/").status_code == 404
    assert client.get("/api/app/companies/999999").status_code == 404


@pytest.mark.parametrize("feature", ["markets", "news", "ipos", "companies"])
def test_detail_feature_gates(client, member, company, feature):
    FeatureBlock.objects.create(user=member, feature=feature)
    client.force_login(member)
    response = client.get(f"/api/app/companies/{company.pk}")
    if feature == "companies":
        assert response.status_code == 403
        assert client.get(f"/companies/{company.pk}/").status_code == 403
        return
    body = response.json()
    assert response.status_code == 200
    if feature == "markets":
        assert body["quote"] is body["outlook"] is None
        assert body["candles"] == []
    elif feature == "news":
        assert body["news"] == []
        assert body["outlook"] is None
    else:
        assert body["ipos"] == []


def test_market_directory_pagination_missing_quotes_and_access(client, member, company):
    Company.objects.create(name="Empty", symbol="EMPTY")
    assert client.get("/api/app/markets/companies").status_code == 401
    client.force_login(member)
    body = client.get("/api/app/markets/companies", {"q": "EXAMPLE"}).json()
    assert body["total"] == 1
    assert body["items"][0]["quote"]["price"] == 110
    body = client.get("/api/app/markets/companies", {"q": "Empty"}).json()
    assert body["items"][0]["quote"] is None
    assert client.get("/markets/live/").status_code == 200
    FeatureBlock.objects.create(user=member, feature="markets")
    assert client.get("/markets/live/").status_code == 403
    assert client.get("/api/app/markets/companies").status_code == 403


def test_changed_mapping_does_not_mix_old_price_and_fundamentals(client, member, company):
    company.upstox_instrument_key = "NSE_EQ|INE040H01021"
    company.save()
    client.force_login(member)
    body = client.get(f"/api/app/companies/{company.pk}").json()
    assert body["quote"] is body["outlook"] is None
    assert body["fundamentals"] == {}
