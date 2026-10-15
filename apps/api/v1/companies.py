"""Companies: `/api/v1/companies`."""

from django.http import HttpRequest
from ninja import Field, Query, Router

from apps.web import queries

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS_WITH_VALIDATION, MAX_SEARCH_CHARS
from .schemas import CompanyPage

router = Router(tags=["Companies"], auth=for_feature("companies"))


class CompanyFilters(PageParams):
    """Filters for the company list."""

    q: str | None = Field(
        None, max_length=MAX_SEARCH_CHARS, description="Text in the name, symbol or sector."
    )


@router.get(
    "/companies",
    response={200: CompanyPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_companies",
    summary="List companies",
)
def list_companies(request: HttpRequest, filters: Query[CompanyFilters]):
    """List the companies that the news matcher knows, sorted by name.

    The Screener.in data is not part of the answer. `last_updated` shows when it was fetched.

    **Required feature:** `companies`.
    """
    return paginate(queries.company_queryset({"q": filters.q or ""}), filters)
