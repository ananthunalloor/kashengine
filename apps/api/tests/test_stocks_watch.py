"""News watchlist evidence, calendar behavior, bounded ranking and feature privacy."""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest

from apps.access.models import FeatureBlock
from apps.api.app.stocks_watch import stocks_to_watch
from apps.companies.models import Company, CompanyOutlook
from apps.markets.models import Prediction, TradingCalendarDay
from apps.news.models import NewsArticle

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 26, 4, 30, tzinfo=UTC)  # Monday, 10:00 IST.


def story(company, score=0.8, relevance=0.9, **overrides):
    """Create scored, dated company evidence with explicit override cases."""
    article = NewsArticle.objects.create(
        **{
            "title": "Company announcement",
            "url": f"https://example.test/news/{NewsArticle.objects.count()}",
            "source": "Wire",
            "published_at": NOW - timedelta(hours=1),
            "scored_at": NOW - timedelta(minutes=30),
            "sentiment_score": score,
            "relevance": relevance,
            "sentiment_reason": "Saved news explanation",
            **overrides,
        }
    )
    article.companies.add(company)
    return article


@pytest.fixture
def company():
    return Company.objects.create(name="Example", symbol="EXAMPLE", sector="Energy")


def test_bias_weighting_source_count_and_saved_evidence(company):
    positive = story(company, 0.8, 1, source="Wire")
    story(company, 0.2, 0.5, source=" wire ")
    data = stocks_to_watch(NOW)
    assert data["session_state"] == "open"
    assert data["session_date"] == data["next_session"] == date(2026, 10, 26)
    assert data["sampled_articles"] == 2
    item = data["items"][0]
    assert item["bias"] == "bullish"
    assert item["score"] == pytest.approx(0.6)
    assert item["attention"] == pytest.approx(0.45)
    assert item["sources"] == 1
    assert item["articles"] == item["positive"] == 2
    assert item["negative"] == 0
    assert item["stories"][0] == positive
    assert item["stories"][0].sentiment_reason == "Saved news explanation"


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ([-0.9], "bearish"),
        ([0], "neutral"),
        ([0.15], "neutral"),
        ([-0.15], "neutral"),
        ([0.9, -0.2], "mixed"),
        ([0.4], "bullish"),
    ],
)
def test_bias_states_and_conflicting_stories(company, scores, expected):
    for score in scores:
        story(company, score)
    assert stocks_to_watch(NOW)["items"][0]["bias"] == expected


def test_excludes_future_old_unscored_undated_low_relevance_and_invalid_scores(company):
    story(company, published_at=NOW + timedelta(seconds=1))
    story(company, published_at=NOW - timedelta(hours=36, seconds=1))
    story(company, published_at=None)
    story(company, scored_at=None)
    story(company, scored_at=NOW + timedelta(seconds=1))
    story(company, score=None)
    story(company, score=1.1)
    story(company, relevance=0.49)
    story(company, relevance=1.1)
    story(company, relevance=None)
    data = stocks_to_watch(NOW)
    assert data["items"] == []
    assert data["sampled_articles"] == 0
    story(company, relevance=0.5, published_at=NOW - timedelta(hours=36))
    assert stocks_to_watch(NOW)["items"][0]["articles"] == 1


def test_company_links_are_deduplicated_and_unlinked_news_is_excluded(company):
    other = Company.objects.create(name="Other", symbol="OTHER")
    article = story(company)
    article.companies.add(other)
    unlinked = story(company)
    unlinked.companies.clear()
    data = stocks_to_watch(NOW)
    assert data["sampled_articles"] == 1
    assert len(data["items"]) == 2
    assert all(item["articles"] == 1 for item in data["items"])


def test_limits_companies_and_headlines_ranks_attention_without_hiding_mixed_news(company):
    for index in range(10):
        candidate = Company.objects.create(name=f"Company {index}", symbol=f"EX{index}")
        story(candidate, score=0.2 + index * 0.05)
    for score in [1, -0.9, 0.9, 0.8, -0.8]:
        story(company, score=score)
    data = stocks_to_watch(NOW)
    assert len(data["items"]) == 8
    assert data["items"][0]["id"] == company.pk
    assert data["items"][0]["bias"] == "mixed"
    assert data["items"][0]["articles"] == 5
    assert len(data["items"][0]["stories"]) == 3
    assert any(story.sentiment_score < 0 for story in data["items"][0]["stories"])


def test_mixed_highlights_include_opposing_evidence_even_when_weaker(company):
    for score in [1, 0.95, 0.9, -0.2]:
        story(company, score=score)
    item = stocks_to_watch(NOW)["items"][0]
    assert item["bias"] == "mixed"
    assert any(article.sentiment_score == -0.2 for article in item["stories"])


def test_flat_threshold_survives_weighted_average_rounding(company):
    for _ in range(20):
        story(company, score=0.15, relevance=0.7)
    item = stocks_to_watch(NOW)["items"][0]
    assert item["bias"] == "neutral"
    assert item["score"] == 0.15


def test_article_sample_is_bounded_and_coverage_truncation_is_explicit(company):
    articles = NewsArticle.objects.bulk_create(
        [
            NewsArticle(
                title=f"Story {index}",
                url=f"https://example.test/{index}",
                source="Wire",
                published_at=NOW - timedelta(minutes=index),
                scored_at=NOW,
                sentiment_score=0.8,
                relevance=1,
            )
            for index in range(302)
        ]
    )
    NewsArticle.companies.through.objects.bulk_create(
        [
            NewsArticle.companies.through(newsarticle_id=article.pk, company_id=company.pk)
            for article in articles
        ]
    )
    result = stocks_to_watch(NOW)
    assert result["sampled_articles"] == 300
    assert result["truncated"] is True
    assert result["items"][0]["articles"] == 300


@pytest.mark.parametrize(
    ("now", "state", "next_day"),
    [
        (datetime(2026, 10, 26, 3, 30, tzinfo=UTC), "pre_open", date(2026, 10, 26)),
        (datetime(2026, 10, 26, 3, 45, tzinfo=UTC), "open", date(2026, 10, 26)),
        (datetime(2026, 10, 26, 10, 0, tzinfo=UTC), "ended", date(2026, 10, 27)),
        (datetime(2026, 10, 25, 4, 30, tzinfo=UTC), "closed", date(2026, 10, 26)),
    ],
)
def test_session_open_close_and_weekend(now, state, next_day):
    result = stocks_to_watch(now)
    assert result["session_state"] == state
    assert result["next_session"] == next_day
    assert result["items"] == []


def test_saved_holidays_and_special_sessions_are_respected(company):
    TradingCalendarDay.objects.create(day=date(2026, 10, 26), kind="holiday", reason="Holiday")
    story(company)
    result = stocks_to_watch(NOW)
    assert result["session_state"] == "closed"
    assert result["items"] == []
    TradingCalendarDay.objects.create(
        day=date(2026, 10, 25),
        kind="special",
        reason="Special weekend session",
        opens_at=time(9, 15),
        closes_at=time(15, 30),
    )
    result = stocks_to_watch(NOW - timedelta(days=1))
    assert result["session_state"] == "open"


def test_closed_market_does_not_read_news_or_invent_today_calls():
    with patch(
        "apps.api.app.stocks_watch.NewsArticle.objects.filter",
        side_effect=AssertionError("Closed-session news read"),
    ):
        result = stocks_to_watch(NOW - timedelta(days=1))
    assert result["items"] == []


@pytest.mark.parametrize("feature", ["companies", "markets", "news"])
def test_feature_gates_prevent_reader_invocation(client, member, feature):
    FeatureBlock.objects.create(user=member, feature=feature)
    client.force_login(member)
    with patch("apps.api.app.today.stocks_to_watch", side_effect=AssertionError("Forbidden read")):
        response = client.get("/api/app/today")
    assert response.status_code == 200
    assert response.json()["stocks_watch"] is None


def test_api_contains_sources_and_never_contacts_providers_or_writes_predictions(
    client, member, company
):
    story(company)
    client.force_login(member)
    before = list(NewsArticle.objects.values())
    forecasts_before = (Prediction.objects.count(), CompanyOutlook.objects.count())
    with (
        patch("apps.api.app.today.timezone.now", return_value=NOW),
        patch("httpx.Client.request", side_effect=AssertionError("Provider called")),
    ):
        response = client.get("/api/app/today")
    assert response.status_code == 200
    item = response.json()["stocks_watch"]["items"][0]
    assert item["name"] == "Example"
    assert item["bias"] == "bullish"
    assert item["stories"][0]["url"].startswith("https://example.test/")
    assert list(NewsArticle.objects.values()) == before
    assert (Prediction.objects.count(), CompanyOutlook.objects.count()) == forecasts_before
