"""Private Markets preview, sharing the legacy page's queries and evaluation rules."""

from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpRequest
from django.template.defaultfilters import floatformat
from django.utils import timezone
from ninja import Field, Query, Router

from apps.api.v1.common import ERRORS, ERRORS_WITH_VALIDATION
from apps.companies.models import Company, CompanyQuote
from apps.markets.evaluation import accuracy_stats
from apps.markets.models import MarketInstrument
from apps.reports.formatting import score_out_of_ten
from apps.siteconfig import conf
from apps.web.queries import latest_quotes, prediction_history
from apps.web.templatetags.web_extras import percent, signed

from .auth import AppSession
from .companies import saved_price
from .schemas import CompanyMarketPage, ExchangeInstrumentPage, Markets
from .tables import TableFilters, ordered

router = Router(tags=["Markets"], auth=AppSession("markets"))


class CompanyMarketFilters(TableFilters):
    """Search the saved directory, including companies without a quote."""

    q: str = Field(default="", max_length=100)


class ExchangeInstrumentFilters(TableFilters):
    """Bound search and supported NSE/BSE catalog filters."""

    q: str = Field(default="", max_length=100)
    exchange: str = Field(default="", pattern="^(|NSE|BSE)$")
    segment: str = Field(default="", pattern="^[A-Z0-9_]{0,20}$")
    instrument_type: str = Field(default="", pattern="^[A-Z0-9_]{0,30}$")
    sort: str = Field(default="", pattern="^(|-?(exchange|trading_symbol|name|expiry))$")


@router.get(
    "/markets/instruments",
    response={200: ExchangeInstrumentPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_exchange_instruments",
    summary="Search active NSE/BSE equity, index, futures, and options instruments",
)
def exchange_instruments(request: HttpRequest, filters: Query[ExchangeInstrumentFilters]):
    """Read the latest imported instrument master without calling the provider."""
    instruments = MarketInstrument.objects.filter(is_active=True)
    if filters.exchange:
        instruments = instruments.filter(exchange=filters.exchange)
    if filters.segment:
        instruments = instruments.filter(segment=filters.segment)
    if filters.instrument_type:
        instruments = instruments.filter(instrument_type=filters.instrument_type)
    if query := filters.q.strip():
        instruments = instruments.filter(
            Q(trading_symbol__icontains=query)
            | Q(name__icontains=query)
            | Q(instrument_key__icontains=query)
            | Q(isin__icontains=query)
            | Q(underlying_symbol__icontains=query)
        )
    instruments = ordered(
        instruments,
        filters.sort,
        {
            "exchange": "exchange",
            "trading_symbol": "trading_symbol",
            "name": "name",
            "expiry": "expiry",
        },
    )
    page = Paginator(instruments, filters.page_size or conf.WEB_PAGE_SIZE).get_page(
        max(1, filters.page)
    )
    segment_rows = MarketInstrument.objects.filter(is_active=True)
    if filters.exchange:
        segment_rows = segment_rows.filter(exchange=filters.exchange)
    type_rows = segment_rows
    return {
        "items": [
            {
                "instrument_key": row.instrument_key,
                "exchange": row.exchange,
                "segment": row.segment,
                "trading_symbol": row.trading_symbol,
                "name": row.name,
                "instrument_type": row.instrument_type,
                "isin": row.isin,
                "underlying_symbol": row.underlying_symbol,
                "expiry": row.expiry,
                "strike_price": float(row.strike_price) if row.strike_price is not None else None,
                "lot_size": row.lot_size,
                "company_id": row.company_id,
            }
            for row in page.object_list
        ],
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "segments": list(
            segment_rows.order_by("segment").values_list("segment", flat=True).distinct()
        ),
        "instrument_types": list(
            type_rows.order_by("instrument_type")
            .values_list("instrument_type", flat=True)
            .distinct()
        ),
    }


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


def company_movers() -> dict:
    """Rank the latest saved company quotes and calculate breadth for that quote set."""
    latest = CompanyQuote.objects.filter(
        company=OuterRef("pk"), instrument_key=OuterRef("upstox_instrument_key")
    ).order_by("-as_of")
    companies = Company.objects.filter(upstox_instrument_key__gt="").annotate(
        quote_id=Subquery(latest.values("pk")[:1])
    )
    companies = companies.exclude(quote_id__isnull=True).only("id", "name", "symbol")
    quotes = CompanyQuote.objects.in_bulk(
        company.quote_id for company in companies if company.quote_id is not None
    )
    changes = []
    for company in companies:
        quote = quotes[company.quote_id]
        if quote.previous_close is None or quote.previous_close <= 0:
            continue
        change_pct = (quote.price / quote.previous_close - 1) * 100
        changes.append(
            {
                "id": company.pk,
                "name": company.name,
                "symbol": company.symbol,
                "price": quote.price,
                "change_pct": change_pct,
                "as_of": quote.as_of,
            }
        )
    latest_day = timezone.localdate(max(row["as_of"] for row in changes)) if changes else None
    changes = [row for row in changes if timezone.localdate(row["as_of"]) == latest_day]
    gainers = [row for row in changes if row["change_pct"] > 0]
    losers = [row for row in changes if row["change_pct"] < 0]
    return {
        "as_of": max((row["as_of"] for row in changes), default=None),
        "coverage": len(changes),
        "advancing": sum(row["change_pct"] > 0 for row in changes),
        "declining": sum(row["change_pct"] < 0 for row in changes),
        "unchanged": sum(row["change_pct"] == 0 for row in changes),
        "gainers": sorted(gainers, key=lambda row: (-row["change_pct"], row["name"]))[:5],
        "losers": sorted(losers, key=lambda row: (row["change_pct"], row["name"]))[:5],
    }


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
                "result": "Withheld"
                if prediction.direction == "withheld"
                else "Right"
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
