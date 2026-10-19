"""Private News preview using the existing web queries and report score formatting."""

from django.core.paginator import Paginator
from django.http import HttpRequest
from ninja import Field, Query, Router, Schema

from apps.api.v1.common import ERRORS_WITH_VALIDATION
from apps.reports.builder import STORY_MIN_SCORE
from apps.reports.formatting import score_out_of_ten
from apps.siteconfig import conf
from apps.web.queries import SENTIMENT_FILTERS, news_queryset, news_sources

from .auth import AppSession
from .schemas import NewsPage

router = Router(tags=["News"], auth=AppSession("news"))


class NewsFilters(Schema):
    """Bound search input to the same lengths as the existing web filters."""

    q: str = Field(default="", max_length=100, description="Headline or summary search text.")
    source: str = Field(default="", max_length=100, description="Exact source name, or all.")
    sentiment: str = Field(
        default="",
        pattern="^(|positive|negative|neutral|unscored)$",
        description="Sentiment category, or empty for all.",
    )
    page: int = Field(default=1, description="Requested page; out-of-range values are clamped.")


@router.get(
    "/news",
    response={200: NewsPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_news",
    summary="Search and filter the browser news feed",
)
def list_news(request: HttpRequest, filters: Query[NewsFilters]):
    """Preserve the existing search, score thresholds, source filters, and display values."""
    values = {
        "q": filters.q.strip(),
        "source": filters.source.strip(),
        "sentiment": filters.sentiment,
    }
    articles = (
        news_queryset(values)
        .defer("text", "summary")
        .order_by("-published_at", "-fetched_at", "-pk")
    )
    result = Paginator(articles, conf.WEB_PAGE_SIZE).get_page(max(1, filters.page))
    items = []
    for article in result.object_list:
        score = article.sentiment_score
        sentiment = (
            "unscored"
            if score is None
            else "positive"
            if score >= STORY_MIN_SCORE
            else "negative"
            if score <= -STORY_MIN_SCORE
            else "neutral"
        )
        items.append(
            {
                "id": article.pk,
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at,
                "sentiment": sentiment,
                "score": score_out_of_ten(score, signed=True) if score is not None else None,
                "relevance": score_out_of_ten(article.relevance)
                if article.relevance is not None
                else None,
                "reason": article.sentiment_reason,
                "companies": [company.name for company in list(article.companies.all())[:4]],
            }
        )
    return {
        "items": items,
        "page": result.number,
        "pages": result.paginator.num_pages,
        "total": result.paginator.count,
        "sources": news_sources(),
        "sentiments": [{"value": key, "label": label} for key, label in SENTIMENT_FILTERS.items()],
    }
