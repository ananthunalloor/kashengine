"""Private company directory preview, sharing the existing name/symbol/sector query."""

from django.core.paginator import Paginator
from django.http import HttpRequest
from ninja import Field, Query, Router, Schema

from apps.api.v1.common import ERRORS_WITH_VALIDATION
from apps.siteconfig import conf
from apps.web.queries import company_queryset

from .auth import AppSession
from .schemas import CompanyPage

router = Router(tags=["Companies"], auth=AppSession("companies"))


class CompanyFilters(Schema):
    """Bound directory search and validate pagination."""

    q: str = Field(default="", max_length=100, description="Name, symbol, or sector search.")
    page: int = Field(default=1, description="Requested page; out-of-range values are clamped.")


@router.get(
    "/companies",
    response={200: CompanyPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_companies",
    summary="Search the company directory",
)
def list_companies(request: HttpRequest, filters: Query[CompanyFilters]):
    """Read display fields without fetching or exposing scraped company data."""
    companies = company_queryset({"q": filters.q.strip()}).defer("aliases", "screener_data")
    page = Paginator(companies, conf.WEB_PAGE_SIZE).get_page(max(1, filters.page))
    return {
        "items": list(page.object_list),
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
    }
