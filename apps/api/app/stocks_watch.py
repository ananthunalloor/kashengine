"""Bounded news-only company watchlist; no provider calls or persisted forecasts."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Prefetch

from apps.companies.models import Company
from apps.markets.trading import (
    is_trading_day,
    next_trading_day,
    session_close,
    session_open,
    today_ist,
)
from apps.news.models import NewsArticle
from apps.web.queries import NEWS_WINDOW_HOURS

ARTICLE_LIMIT = 300
COMPANY_LIMIT = 8
EVIDENCE_LIMIT = 3
MIN_RELEVANCE = 0.5
BIAS_THRESHOLD = 0.15


@dataclass
class CompanyEvidence:
    """Aggregate unique saved articles linked to one company."""

    company: Company
    stories: list[NewsArticle] = field(default_factory=list)


def watch_item(evidence: CompanyEvidence) -> dict:
    """Describe sentiment balance without calling it a calibrated movement probability."""
    stories = evidence.stories
    total_weight = sum(story.relevance for story in stories)
    score = round(
        sum(story.sentiment_score * story.relevance for story in stories) / total_weight, 12
    )
    positive = sum(story.sentiment_score > BIAS_THRESHOLD for story in stories)
    negative = sum(story.sentiment_score < -BIAS_THRESHOLD for story in stories)
    bias = (
        "mixed"
        if positive and negative
        else "bullish"
        if score > BIAS_THRESHOLD
        else "bearish"
        if score < -BIAS_THRESHOLD
        else "neutral"
    )
    ranked = sorted(
        stories,
        key=lambda story: (
            abs(story.sentiment_score) * story.relevance,
            story.published_at,
            story.pk,
        ),
        reverse=True,
    )
    highlighted = ranked[:EVIDENCE_LIMIT]
    if bias == "mixed":
        opposing = [
            next(story for story in ranked if story.sentiment_score > BIAS_THRESHOLD),
            next(story for story in ranked if story.sentiment_score < -BIAS_THRESHOLD),
        ]
        selected_ids = {story.pk for story in opposing}
        highlighted = (opposing + [story for story in ranked if story.pk not in selected_ids])[
            :EVIDENCE_LIMIT
        ]
    return {
        "id": evidence.company.pk,
        "name": evidence.company.name,
        "symbol": evidence.company.symbol,
        "sector": evidence.company.sector,
        "bias": bias,
        "score": score,
        "attention": sum(abs(story.sentiment_score) * story.relevance for story in stories)
        / len(stories),
        "articles": len(stories),
        "sources": len(
            {story.source.strip().casefold() for story in stories if story.source.strip()}
        ),
        "positive": positive,
        "negative": negative,
        "latest_news_at": max(story.published_at for story in stories),
        "stories": highlighted,
    }


def stocks_to_watch(now: datetime) -> dict:
    """Summarize up to 300 recent scored stories into eight company-linked news biases.

    The caller must check Companies, Markets and News access before invoking this reader.
    Closed days and completed sessions return no today's movement suggestions.
    """
    today = today_ist(now)
    trading = is_trading_day(today)
    state = (
        "closed"
        if not trading
        else "ended"
        if now >= session_close(today)
        else "pre_open"
        if now < session_open(today)
        else "open"
    )
    result = {
        "as_of": now,
        "since": now - timedelta(hours=NEWS_WINDOW_HOURS),
        "session_date": today,
        "next_session": next_trading_day(today + timedelta(days=1))
        if state in {"closed", "ended"}
        else today,
        "session_state": state,
        "sampled_articles": 0,
        "truncated": False,
        "items": [],
    }
    if state in {"closed", "ended"}:
        return result
    stories = list(
        NewsArticle.objects.filter(
            published_at__gte=result["since"],
            published_at__lte=now,
            scored_at__lte=now,
            sentiment_score__gte=-1,
            sentiment_score__lte=1,
            relevance__gte=MIN_RELEVANCE,
            relevance__lte=1,
            companies__isnull=False,
        )
        .distinct()
        .only(
            "id",
            "title",
            "url",
            "source",
            "published_at",
            "sentiment_score",
            "sentiment_reason",
            "relevance",
        )
        .order_by("-published_at", "-pk")
        .prefetch_related(
            Prefetch("companies", queryset=Company.objects.only("id", "name", "symbol", "sector"))
        )[: ARTICLE_LIMIT + 1]
    )
    result["truncated"] = len(stories) > ARTICLE_LIMIT
    stories = stories[:ARTICLE_LIMIT]
    result["sampled_articles"] = len(stories)
    companies: dict[int, CompanyEvidence] = {}
    for story in stories:
        for company in story.companies.all():
            companies.setdefault(company.pk, CompanyEvidence(company)).stories.append(story)
    items = [watch_item(evidence) for evidence in companies.values()]
    result["items"] = sorted(
        items,
        key=lambda item: (-item["attention"], -item["latest_news_at"].timestamp(), item["symbol"]),
    )[:COMPANY_LIMIT]
    return result
