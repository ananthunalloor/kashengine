"""News articles: `/api/v1/news`."""

from datetime import datetime

from django.http import HttpRequest
from ninja import Field, Query, Router

from apps.web import queries

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS_WITH_VALIDATION, MAX_SEARCH_CHARS
from .schemas import NewsPage, Sentiment

router = Router(tags=["News"], auth=for_feature("news"))


class NewsFilters(PageParams):
    """Filters for the news list. All filters are optional and they combine with AND."""

    q: str | None = Field(
        None, max_length=MAX_SEARCH_CHARS, description="Text in the title or the summary."
    )
    sentiment: Sentiment | None = Field(
        None, description="Only articles with this sentiment. `unscored` means not scored yet."
    )
    source: str | None = Field(
        None, max_length=MAX_SEARCH_CHARS, description="The exact source name, for example Mint."
    )
    since: datetime | None = Field(
        None, description="Only articles published at or after this time (ISO 8601)."
    )


@router.get(
    "/news",
    response={200: NewsPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_news",
    summary="List news articles",
)
def list_news(request: HttpRequest, filters: Query[NewsFilters]):
    """List scored news articles, newest first.

    An article carries the sentiment from the local language model and the companies that the
    matcher found in it. The full article text is never part of the API.

    **Required feature:** `news`.
    """
    articles = queries.news_queryset(
        {"q": filters.q or "", "sentiment": filters.sentiment or "", "source": filters.source or ""}
    )
    if filters.since is not None:
        articles = articles.filter(published_at__gte=filters.since)
    return paginate(articles, filters)
