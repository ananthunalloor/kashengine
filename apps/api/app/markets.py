"""Private Markets preview, sharing the legacy page's queries and evaluation rules."""

from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from django.http import HttpRequest
from django.template.defaultfilters import floatformat
from ninja import Field, Query, Router

from apps.api.v1.common import ERRORS, ERRORS_WITH_VALIDATION
from apps.companies.models import Company, CompanyQuote
from apps.markets.evaluation import accuracy_stats
from apps.reports.formatting import score_out_of_ten
from apps.siteconfig import conf
from apps.web.queries import latest_quotes, prediction_history
from apps.web.templatetags.web_extras import percent, signed

from .auth import AppSession
from .companies import saved_price
from .schemas import CompanyMarketPage, Markets
from .tables import TableFilters

router = Router(tags=["Markets"], auth=AppSession("markets"))


class CompanyMarketFilters(TableFilters):
    """Search the saved directory, including companies without a quote."""

    q: str = Field(default="", max_length=100)


@router.get(
    "/markets/companies",
    response={200: CompanyMarketPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_company_markets",
    summary="Read saved company market observations",
)
def company_markets(request: HttpRequest, filters: Query[CompanyMarketFilters]):
    """Reuse persisted snapshots only, with pagination before quote hydration."""
    latest = CompanyQuote.objects.filter(
        company=OuterRef("pk"), instrument_key=OuterRef("upstox_instrument_key")
    ).order_by("-as_of")
    companies = Company.objects.filter(name__icontains=filters.q.strip()) | Company.objects.filter(
        symbol__icontains=filters.q.strip()
    )
    companies = companies.only("id", "name", "symbol", "upstox_errors", "upstox_instrument_key")
    companies = companies.annotate(quote_id=Subquery(latest.values("pk")[:1]))
    page = Paginator(companies, filters.page_size or conf.WEB_PAGE_SIZE).get_page(
        max(1, filters.page)
    )
    quotes = CompanyQuote.objects.in_bulk(
        company.quote_id for company in page.object_list if company.quote_id is not None
    )
    return {
        "items": [
            {
                "id": company.pk,
                "name": company.name,
                "symbol": company.symbol,
                "quote": saved_price(quotes.get(company.quote_id)),
                "error": company.upstox_errors.get("quotes", ""),
            }
            for company in page.object_list
        ],
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "upstox_enabled": conf.UPSTOX_ENABLED,
    }


def market_stats() -> dict:
    """Format saved accuracy statistics for the private Markets and Today pages.

    Returns:
        Existing evaluation statistics with formatted accuracy and baseline percentages.
    """
    stats = accuracy_stats()
    return {
        **stats,
        "accuracy": percent(stats["accuracy"]),
        "baseline_accuracy": percent(stats["baseline_accuracy"]),
    }


def market_quotes() -> list[dict]:
    """Format the latest configured closes without fetching new prices.

    Returns:
        Instrument names, actual trading dates, closes and signed percentage changes.
    """
    return [
        {
            "name": quote["name"],
            "day": quote["day"],
            "close": floatformat(quote["close"], 2),
            "change": f"{signed(quote['change_pct'], 2)}%"
            if quote["change_pct"] is not None
            else "–",
        }
        for quote in latest_quotes()
    ]


@router.get(
    "/markets",
    response={200: Markets, **ERRORS},
    operation_id="get_app_markets",
    summary="Read market closes, prediction history, and accuracy",
)
def get_markets(request: HttpRequest):
    """Read saved results without fetching quotes or evaluating predictions."""
    return {
        "stats": market_stats(),
        "quotes": market_quotes(),
        "history": [
            {
                "date": prediction.target_date,
                "direction": prediction.direction,
                "strength": score_out_of_ten(prediction.confidence),
                "actual_direction": prediction.actual_direction,
                "change": f"{signed(prediction.actual_change_pct, 2)}%"
                if prediction.actual_change_pct is not None
                else "–",
                "result": "Right"
                if prediction.correct is True
                else "Wrong"
                if prediction.correct is False
                else "No session"
                if prediction.evaluated_at
                else "Waiting",
            }
            for prediction in prediction_history()
        ],
    }
