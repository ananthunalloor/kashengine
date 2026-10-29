"""News preview display parity, bounded filters, and server-side authorization."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.companies.models import Company
from apps.news.models import NewsArticle
from apps.siteconfig import conf
from apps.web.queries import news_queryset

pytestmark = pytest.mark.django_db
URL = "/api/app/news"


def article(title, score=None, **kwargs):
    """Create an article with realistic scoring timestamps for filter tests."""
    return NewsArticle.objects.create(
        title=title,
        url=f"https://example.test/{title}",
        source=kwargs.pop("source", "Mint"),
        sentiment_score=score,
        scored_at=timezone.now() if score is not None else None,
        coverage=kwargs.pop("coverage", "india"),
        region=kwargs.pop("region", "India"),
        **kwargs,
    )


def test_news_requires_a_session_and_the_feature(client, member, make_token, auth):
    assert client.get(URL).status_code == 401
    client.force_login(member)
    _, secret = make_token(member)
    assert client.get(URL, headers=auth(secret)).status_code == 401
    FeatureBlock.objects.create(user=member, feature="news")
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "feature_not_available"
    assert client.get("/news/").status_code == 403


def test_expired_subscription_cannot_read_news(client, member, settings, expire):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(member)
    client.force_login(member)
    assert client.get(URL).json()["code"] == "subscription_required"
    assert client.get("/news/").status_code == 302


def test_staff_remains_exempt_and_public_api_switch_is_independent(client, staff, settings, expire):
    settings.SUBSCRIPTIONS_REQUIRED = True
    settings.API_ENABLED = False
    conf.invalidate()
    expire(staff)
    FeatureBlock.objects.create(user=staff, feature="news")
    client.force_login(staff)
    assert client.get(URL).status_code == 200


@pytest.mark.parametrize("sentiment", ["", "positive", "negative", "neutral", "unscored"])
def test_filters_reuse_existing_web_thresholds(client, member, sentiment):
    for title, score in [("positive", 0.2), ("negative", -0.2), ("neutral", 0), ("unscored", None)]:
        article(title, score)
    client.force_login(member)
    body = client.get(URL, {"sentiment": sentiment}).json()
    existing = news_queryset({"q": "", "source": "", "sentiment": sentiment})
    assert {item["id"] for item in body["items"]} == set(existing.values_list("pk", flat=True))


def test_combined_search_source_and_pagination(client, member, settings):
    settings.WEB_PAGE_SIZE = 1
    conf.invalidate()
    now = timezone.now()
    first = article("Banks rebound", 0.5, published_at=now, summary="Credit improves")
    second = article("Banks grow", 0.7, published_at=now - timedelta(hours=1))
    article("Other", -0.6, source="Other source")
    article("Unrelated", 0.5)
    client.force_login(member)
    filters = {"q": "  banks  ", "source": "Mint", "sentiment": "positive"}
    body = client.get(URL, filters).json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert body["items"][0]["id"] == first.pk
    assert body["sources"] == ["Mint", "Other source"]
    assert client.get(URL, {**filters, "page": 2}).json()["items"][0]["id"] == second.pk
    assert client.get(URL, {**filters, "page": 999}).json()["page"] == 2
    assert client.get(URL, {"q": "Credit"}).json()["items"][0]["id"] == first.pk
    assert client.get(URL, {"page": -1}).json()["page"] == 1


def test_coverage_filter_returns_region_metadata(client, member):
    domestic = article("RBI holds rates", coverage="india", region="West India")
    article("US Fed signals cut", coverage="international", region="North America")
    client.force_login(member)

    response = client.get(URL, {"coverage": "india"})
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == domestic.pk
    assert response.json()["items"][0]["coverage"] == "india"
    assert response.json()["items"][0]["region"] == "West India"
    assert client.get(URL, {"coverage": "unknown"}).status_code == 422


def test_display_values_nulls_company_limit_and_private_headers(client, member):
    row = article("Scored", 0, relevance=0, sentiment_reason="<b>Plain text</b>")
    row.companies.add(
        *[Company.objects.create(name=f"Company {i}", symbol=f"C{i}") for i in range(5)]
    )
    article("Not scored")
    client.force_login(member)
    response = client.get(URL)
    items = {item["title"]: item for item in response.json()["items"]}
    assert items["Scored"]["score"] == "5.5/10"
    assert items["Scored"]["relevance"] == "1.0/10"
    assert items["Scored"]["reason"] == "<b>Plain text</b>"
    assert items["Scored"]["sentiment"] == "neutral"
    assert len(items["Scored"]["companies"]) == 4
    assert items["Not scored"]["score"] is None
    assert items["Not scored"]["relevance"] is None
    assert items["Not scored"]["published_at"] is None
    assert "text" not in items["Scored"]
    assert "summary" not in items["Scored"]
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize(
    "params",
    [
        {"page": "bad"},
        {"q": "x" * 101},
        {"source": "x" * 101},
        {"sentiment": "invalid"},
    ],
)
def test_invalid_filters_are_explicit_problem_responses(client, member, params):
    client.force_login(member)
    response = client.get(URL, params)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_empty_news_has_options_and_preserves_original_page(client, member):
    assert client.get("/news/").status_code == 302
    client.force_login(member)
    response = client.get("/news/")
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert "no-store" in response["Cache-Control"]
    assert "web/spa.html" in [template.name for template in client.get("/news/").templates]
    body = client.get(URL).json()
    assert body["items"] == []
    assert body["page"] == body["pages"] == 1
    assert body["total"] == 0
    assert {option["value"] for option in body["sentiments"]} == {
        "positive",
        "negative",
        "neutral",
        "unscored",
    }
