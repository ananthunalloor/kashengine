"""Private company directory preview, sharing the existing name/symbol/sector query."""

from django.core.paginator import Paginator
from django.http import HttpRequest
from ninja import Field, Query, Router

from apps.api.v1.common import ERRORS_WITH_VALIDATION
from apps.siteconfig import conf
from apps.web.queries import company_queryset

from .auth import AppSession
from .schemas import CompanyPage
from .tables import TableFilters, ordered

router = Router(tags=["Companies"], auth=AppSession("companies"))


class CompanyFilters(TableFilters):
    """Bound directory search and validate pagination."""

    q: str = Field(default="", max_length=100, description="Name, symbol, or sector search.")
    sector: str = Field(default="", max_length=100, description="Exact sector, or all.")
    sort: str = Field(default="", pattern="^(|-?(name|symbol|sector|last_updated))$")


@router.get(
    "/companies",
    response={200: CompanyPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_companies",
    summary="Search the company directory",
)
def list_companies(request: HttpRequest, filters: Query[CompanyFilters]):
    """Read display fields without fetching or exposing scraped company data."""
    companies = company_queryset({"q": filters.q.strip()}).defer("aliases", "screener_data")
    if filters.sector:
        companies = companies.filter(sector=filters.sector)
    companies = ordered(
        companies,
        filters.sort,
        {
            "name": "name",
            "symbol": "symbol",
            "sector": "sector",
            "last_updated": "last_updated",
        },
    )
    page = Paginator(companies, filters.page_size or conf.WEB_PAGE_SIZE).get_page(
        max(1, filters.page)
    )
    return {
        "items": list(page.object_list),
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "sectors": list(
            company_queryset({"q": ""})
            .exclude(sector="")
            .order_by("sector")
            .values_list("sector", flat=True)
            .distinct()
        ),
    }
