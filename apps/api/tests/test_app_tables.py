"""Private tables sort/filter complete querysets before bounded pagination."""

from datetime import date

import pytest
from django.utils import timezone

from apps.companies.models import Company
from apps.ipos.models import Ipo
from apps.news.models import NewsArticle
from apps.reports.models import Report

pytestmark = pytest.mark.django_db
PATHS = ["/api/app/reports", "/api/app/news", "/api/app/ipos", "/api/app/companies"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "params",
    [
        {"sort": "recipient"},
        {"sort": "name;DROP TABLE"},
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": "oops"},
        {"q": "x" * 101},
    ],
)
def test_table_inputs_are_bounded(client, member, path, params):
    client.force_login(member)
    response = client.get(path, params)
    assert response.status_code == 422
    assert response["Content-Type"] == "application/problem+json"


def test_companies_filter_and_sort_before_pagination(client, member):
    Company.objects.create(name="Zebra", symbol="Z", sector="Tech")
    Company.objects.create(name="Alpha", symbol="A", sector="Finance")
    Company.objects.create(name="Beta", symbol="B", sector="Tech")
    client.force_login(member)
    body = client.get(
        "/api/app/companies", {"sector": "Tech", "sort": "name", "page_size": 1}
    ).json()
    assert body["total"] == body["pages"] == 2
    assert body["page_size"] == 1
    assert body["items"][0]["name"] == "Beta"
    assert body["sectors"] == ["Finance", "Tech"]
    second = client.get(
        "/api/app/companies",
        {
            "sector": "Tech",
            "sort": "-name",
            "page_size": 1,
            "page": 2,
        },
    ).json()
    assert second["items"][0]["name"] == "Beta"
    assert (
        client.get("/api/app/companies", {"sector": "Finance", "q": "zebra"}).json()["total"] == 0
    )


def test_ipo_numeric_sort_uses_raw_values_and_nulls_last(client, member):
    for name, score, gmp in [("Small", -1, -5), ("Large", 1, 100), ("Missing", None, None)]:
        Ipo.objects.create(name=name, score=score, gmp=gmp, price_band_high=100, status="open")
    client.force_login(member)
    for sort in ("score", "gmp"):
        body = client.get("/api/app/ipos", {"sort": sort, "page_size": 1, "page": 2}).json()
        assert body["items"][0]["name"] == "Large"
        descending = client.get("/api/app/ipos", {"sort": f"-{sort}", "page_size": 2}).json()
        assert [row["name"] for row in descending["items"]] == ["Large", "Small"]
    assert (
        client.get("/api/app/ipos", {"sort": "-score", "page": 999, "page_size": 1}).json()[
            "items"
        ][0]["name"]
        == "Missing"
    )


def test_news_scores_sorted_numerically_across_pages(client, member):
    for index, score in enumerate([0.9, None, -0.8, 0]):
        NewsArticle.objects.create(
            title=f"Article {index}",
            source="Mint",
            url=f"https://example.test/{index}",
            sentiment_score=score,
            published_at=timezone.now(),
        )
    client.force_login(member)
    body = client.get("/api/app/news", {"sort": "score", "page_size": 2}).json()
    assert [row["score"] for row in body["items"]] == ["1.9/10", "5.5/10"]
    second = client.get("/api/app/news", {"sort": "score", "page_size": 2, "page": 2}).json()
    assert [row["score"] for row in second["items"]] == ["9.5/10", None]
    filtered = client.get(
        "/api/app/news", {"sentiment": "negative", "sort": "-score", "page_size": 1}
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["title"] == "Article 2"


def test_gmp_sort_is_percentage_not_rupee_amount_and_zero_price_is_missing(client, member):
    Ipo.objects.create(name="One percent", gmp=20, price_band_high=2000, status="open")
    Ipo.objects.create(name="Ten percent", gmp=10, price_band_high=100, status="open")
    Ipo.objects.create(name="Zero price", gmp=99, price_band_high=0, status="open")
    client.force_login(member)
    body = client.get("/api/app/ipos", {"sort": "-gmp"}).json()
    assert [row["name"] for row in body["items"]] == ["Ten percent", "One percent", "Zero price"]
    assert [row["gmp"] for row in body["items"]] == ["+10.0%", "+1.0%", "–"]


def test_report_text_date_outlook_search_and_strength_sort(client, member):
    Report.objects.create(
        date=date(2026, 10, 16), text="Banks rebound", prediction="up", confidence=0.9
    )
    Report.objects.create(
        date=date(2026, 10, 15), text="Banks fall", prediction="down", confidence=0.1
    )
    Report.objects.create(date=date(2026, 10, 14), text="No outlook")
    client.force_login(member)
    path = "/api/app/reports"
    assert client.get(path, {"q": "banks"}).json()["total"] == 2
    assert client.get(path, {"q": "2026-10-16"}).json()["total"] == 1
    filtered = client.get(path, {"q": "banks", "direction": "down", "page_size": 1}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["date"] == "2026-10-15"
    body = client.get(path, {"sort": "strength", "page_size": 1}).json()
    assert body["items"][0]["strength"] == "1.9/10"
    assert client.get(path, {"direction": "unknown"}).json()["items"][0]["date"] == "2026-10-14"
    assert client.get(path, {"direction": "invalid"}).status_code == 422
