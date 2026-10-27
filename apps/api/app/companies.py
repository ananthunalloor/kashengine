"""Private company directory preview, sharing the existing name/symbol/sector query."""

from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, Query, Router

from apps.access.middleware import access_for
from apps.api.v1.common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.companies.models import Company, CompanyQuote
from apps.markets.index_constituents import INDEXES
from apps.markets.models import IndexConstituent, MarketInstrument
from apps.siteconfig import conf
from apps.web.queries import company_queryset

from .auth import AppSession
from .schemas import CompanyDetail, CompanyPage
from .tables import TableFilters, ordered

router = Router(tags=["Companies"], auth=AppSession("companies"))


def company_item(company: Company, listings: list[MarketInstrument] | None = None) -> dict:
    """Return display-safe company fields and all active exchange equity listings."""
    if listings is None:
        listings = list(
            MarketInstrument.objects.filter(
                company=company,
                is_active=True,
                segment__in=["NSE_EQ", "BSE_EQ"],
            ).order_by("exchange", "trading_symbol")
        )
    return {
        "id": company.pk,
        "name": company.name,
        "symbol": company.symbol,
        "listings": [
            {
                "exchange": listing.exchange,
                "symbol": listing.trading_symbol,
                "instrument_key": listing.instrument_key,
            }
            for listing in listings
        ],
        "sector": company.sector,
        "screener_url": company.screener_url,
        "last_updated": company.last_updated,
    }


def saved_price(quote: CompanyQuote | None) -> dict | None:
    """Return a saved price in the form of the API.

    The answer has the time of the exchange (`as_of`) and the time of receipt, so the page can show
    how old the price is. The code never calls a price live.

    Args:
        quote: The newest saved quote of a company, or None.

    Returns:
        None if there is no quote. Else a dict with `as_of`, `received_at`, `price`,
        `previous_close`, `change_pct` (None without a previous close), `volume` and `mode`
        (`snapshot` or `stream`).
    """
    if quote is None:
        return None
    return {
        "as_of": quote.as_of,
        "received_at": quote.received_at,
        "price": quote.price,
        "previous_close": quote.previous_close,
        "change_pct": (quote.price / quote.previous_close - 1) * 100
        if quote.previous_close
        else None,
        "volume": quote.volume,
        "mode": quote.mode,
    }


@router.get(
    "/companies/{pk}",
    response={200: CompanyDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_app_company",
    summary="Read saved company facts, prices and score evidence",
)
def get_company(request: HttpRequest, pk: int):
    """Never contact providers or recalculate scores while reading a company."""
    company = get_object_or_404(Company, pk=pk)
    access = access_for(request)
    markets, news, ipos = (access.can(key) for key in ("markets", "news", "ipos"))
    fundamentals = company.fundamentals.filter(instrument_key=company.upstox_instrument_key).first()
    data = fundamentals.data if fundamentals else company.screener_data
    profile = data.get("profile", {})
    outlook = (
        company.outlooks.filter(inputs__instrument_key=company.upstox_instrument_key).first()
        if markets and news
        else None
    )
    return {
        "company": company_item(company),
        "summary": profile.get("company_profile", "") if isinstance(profile, dict) else "",
        "instrument_key": company.upstox_instrument_key,
        "fundamentals": data,
        "fundamentals_source": "Upstox" if fundamentals else "Screener.in" if data else "",
        "fundamentals_as_of": fundamentals.fetched_at if fundamentals else company.last_updated,
        "errors": {
            key: value
            for key, value in company.upstox_errors.items()
            if markets or key == "fundamentals"
        },
        "markets_available": markets,
        "news_available": news,
        "ipos_available": ipos,
        "quote": saved_price(
            company.quotes.filter(instrument_key=company.upstox_instrument_key).first()
        )
        if markets
        else None,
        "candles": list(
            company.candles.filter(instrument_key=company.upstox_instrument_key).order_by("-day")[
                :365
            ]
        )[::-1]
        if markets
        else [],
        "outlook": outlook,
        "outlook_history": list(
            company.outlooks.filter(inputs__instrument_key=company.upstox_instrument_key)[:120]
        )
        if markets and news
        else [],
        "news": list(company.news_articles.all()[:30]) if news else [],
        "ipos": list(company.ipos.all()[:30]) if ipos else [],
    }


class CompanyFilters(TableFilters):
    """Bound directory search and validate pagination."""

    q: str = Field(default="", max_length=100, description="Name, symbol, or sector search.")
    sector: str = Field(default="", max_length=100, description="Exact sector, or all.")
    index: str = Field(
        default="",
        pattern=r"^($|NIFTY_50|NIFTY_NEXT_50|NIFTY_100|NIFTY_200|NIFTY_500|NIFTY_MIDCAP_50|NIFTY_MIDCAP_100|NIFTY_MIDCAP_150|NIFTY_SMALLCAP_50|NIFTY_SMALLCAP_100|NIFTY_SMALLCAP_250)$",
    )
    sort: str = Field(default="", pattern="^(|-?(name|symbol|sector|last_updated))$")


@router.get(
    "/companies",
    response={200: CompanyPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_companies",
    summary="Search the company directory",
)
def list_companies(request: HttpRequest, filters: Query[CompanyFilters]):
    """Read display fields without fetching or exposing scraped company data."""
    listing_rows = MarketInstrument.objects.filter(
        is_active=True,
        segment__in=["NSE_EQ", "BSE_EQ"],
    ).order_by("exchange", "trading_symbol")
    companies = (
        company_queryset({"q": filters.q.strip()})
        .defer("aliases", "screener_data")
        .prefetch_related(
            Prefetch("market_instruments", queryset=listing_rows, to_attr="active_equity_listings")
        )
    )
    if filters.sector:
        companies = companies.filter(sector=filters.sector)
    if filters.index:
        companies = companies.filter(index_memberships__index_code=filters.index).distinct()
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
    index_counts = dict(
        IndexConstituent.objects.filter(company__isnull=False)
        .values_list("index_code")
        .annotate(count=Count("company_id", distinct=True))
    )
    return {
        "items": [
            company_item(company, company.active_equity_listings) for company in page.object_list
        ],
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
        "indices": [
            {"value": code, "label": label, "count": index_counts.get(code, 0)}
            for code, label, _filename in INDEXES
        ],
    }
