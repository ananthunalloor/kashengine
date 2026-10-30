"""Private company directory preview, sharing the existing name/symbol/sector query."""

from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Prefetch, Subquery
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Query, Router, Status

from apps.access.middleware import access_for
from apps.api.errors import ApiError
from apps.api.v1.common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.companies.models import (
    Company,
    CompanyPriceAlert,
    CompanyQuote,
    CompanyWatchlistEntry,
)
from apps.markets.index_constituents import INDEXES
from apps.markets.models import IndexConstituent, MarketInstrument
from apps.ops.jobs import JOBS_BY_KEY, JobBusyError, JobDispatchError, active_run, start_job
from apps.ops.models import TaskRun
from apps.siteconfig import conf
from apps.web.queries import company_queryset

from .auth import AppSession, OpsSession
from .schemas import (
    CompanyDetail,
    CompanyPage,
    WatchlistAction,
    WatchlistChange,
    WatchlistNotification,
    WatchlistPage,
    WatchlistPriceAlertCreate,
)
from .schemas import WatchlistPriceAlert as WatchlistPriceAlertSchema
from .tables import TableFilters, ordered

router = Router(tags=["Companies"], auth=AppSession("companies"))
COMPANY_LIST_REFRESH_JOB = JOBS_BY_KEY["refresh-exchange-instruments"]


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


def watchlist_alert_item(alert: CompanyPriceAlert) -> dict:
    """Return display-safe threshold and trigger fields."""
    return {
        "id": alert.pk,
        "above_price": alert.above_price,
        "is_active": alert.is_active,
        "created_at": alert.created_at,
        "triggered_at": alert.triggered_at,
        "triggered_price": alert.triggered_price,
    }


def require_markets_access(request: HttpRequest) -> None:
    """Keep saved market data and price alerts behind the Markets feature."""
    if not access_for(request).can("markets"):
        raise ApiError("feature_not_available", "Markets access is required for price alerts.")


@router.get(
    "/watchlist",
    response={200: WatchlistPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_watchlist",
    summary="Read the current user's bookmarked companies and price alerts",
)
def list_watchlist(request: HttpRequest):
    """Read bookmarks, and include market prices and alerts only with Markets access."""
    markets_available = access_for(request).can("markets")
    entries_query = (
        CompanyWatchlistEntry.objects.filter(user=request.user)
        .select_related("company")
        .prefetch_related("price_alerts")
    )
    if markets_available:
        latest_quote_id = (
            CompanyQuote.objects.filter(
                company_id=OuterRef("company_id"),
                instrument_key=OuterRef("company__upstox_instrument_key"),
            )
            .order_by("-as_of", "-pk")
            .values("pk")[:1]
        )
        entries_query = entries_query.annotate(latest_quote_id=Subquery(latest_quote_id))
    entries = list(entries_query)
    quote_ids = (
        [entry.latest_quote_id for entry in entries if entry.latest_quote_id]
        if markets_available
        else []
    )
    quotes = {quote.pk: quote for quote in CompanyQuote.objects.filter(pk__in=quote_ids)}
    return {
        "items": [
            {
                "id": entry.pk,
                "company": {
                    "id": entry.company_id,
                    "name": entry.company.name,
                    "symbol": entry.company.symbol,
                    "sector": entry.company.sector,
                },
                "quote": saved_price(quotes.get(entry.latest_quote_id))
                if markets_available
                else None,
                "alerts": [watchlist_alert_item(alert) for alert in entry.price_alerts.all()]
                if markets_available
                else [],
            }
            for entry in entries
        ]
    }


@router.get(
    "/watchlist/notifications",
    response={200: list[WatchlistNotification], **ERRORS_WITH_VALIDATION},
    operation_id="list_app_watchlist_notifications",
    summary="Read the current user's unread triggered price alerts",
)
def list_watchlist_notifications(request: HttpRequest):
    """Return a bounded list of unread price-crossing notifications."""
    require_markets_access(request)
    alerts = (
        CompanyPriceAlert.objects.filter(
            watchlist_entry__user=request.user,
            is_active=False,
            triggered_at__isnull=False,
            notification_read_at__isnull=True,
        )
        .select_related("watchlist_entry__company")
        .order_by("-triggered_at", "-pk")[:20]
    )
    return [
        {
            "id": alert.pk,
            "company_id": alert.watchlist_entry.company_id,
            "company_name": alert.watchlist_entry.company.name,
            "symbol": alert.watchlist_entry.company.symbol,
            "above_price": alert.above_price,
            "triggered_price": alert.triggered_price,
            "triggered_at": alert.triggered_at,
        }
        for alert in alerts
    ]


@router.put(
    "/watchlist/{company_id}",
    response={200: WatchlistChange, **ERRORS_WITH_NOT_FOUND},
    operation_id="add_app_watchlist_company",
    summary="Bookmark a company in the current user's watchlist",
)
def add_watchlist_company(request: HttpRequest, company_id: int):
    """Add a company once, returning the same success for an existing bookmark."""
    company = get_object_or_404(Company, pk=company_id)
    CompanyWatchlistEntry.objects.get_or_create(user=request.user, company=company)
    return {"watchlisted": True}


@router.delete(
    "/watchlist/{company_id}",
    response={200: WatchlistChange, **ERRORS_WITH_NOT_FOUND},
    operation_id="remove_app_watchlist_company",
    summary="Remove a company and its alerts from the current user's watchlist",
)
def remove_watchlist_company(request: HttpRequest, company_id: int):
    """Remove only the current user's bookmark and its associated alerts."""
    entry = get_object_or_404(CompanyWatchlistEntry, user=request.user, company_id=company_id)
    entry.delete()
    return {"watchlisted": False}


@router.post(
    "/watchlist/{company_id}/alerts",
    response={201: WatchlistPriceAlertSchema, **ERRORS_WITH_NOT_FOUND, **ERRORS_WITH_VALIDATION},
    operation_id="create_app_watchlist_price_alert",
    summary="Notify once when a watched company's price rises above a threshold",
)
def create_watchlist_price_alert(
    request: HttpRequest, company_id: int, body: WatchlistPriceAlertCreate
):
    """Create an independent one-shot threshold alert for a bookmarked company."""
    require_markets_access(request)
    entry = get_object_or_404(
        CompanyWatchlistEntry.objects.select_related("company"),
        user=request.user,
        company_id=company_id,
    )
    alert = CompanyPriceAlert.objects.create(
        watchlist_entry=entry,
        above_price=body.above_price,
    )
    return Status(201, watchlist_alert_item(alert))


@router.delete(
    "/watchlist/alerts/{alert_id}",
    response={200: WatchlistAction, **ERRORS_WITH_NOT_FOUND},
    operation_id="delete_app_watchlist_price_alert",
    summary="Delete one of the current user's price alerts",
)
def delete_watchlist_price_alert(request: HttpRequest, alert_id: int):
    """Delete an alert only when it belongs to the current user's watchlist."""
    alert = get_object_or_404(
        CompanyPriceAlert,
        pk=alert_id,
        watchlist_entry__user=request.user,
    )
    alert.delete()
    return {"ok": True}


@router.post(
    "/watchlist/notifications/{alert_id}/read",
    response={200: WatchlistAction, **ERRORS_WITH_NOT_FOUND},
    operation_id="mark_app_watchlist_notification_read",
    summary="Mark one of the current user's price notifications as read",
)
def mark_watchlist_notification_read(request: HttpRequest, alert_id: int):
    """Acknowledge an unread notification only for its owner."""
    require_markets_access(request)
    alert = get_object_or_404(
        CompanyPriceAlert,
        pk=alert_id,
        watchlist_entry__user=request.user,
        is_active=False,
        triggered_at__isnull=False,
    )
    if alert.notification_read_at is None:
        alert.notification_read_at = timezone.now()
        alert.save(update_fields=["notification_read_at"])
    return {"ok": True}


@router.get(
    "/company-catalog/refresh/{task_id}",
    response={200: dict, **ERRORS_WITH_NOT_FOUND},
    auth=OpsSession(),
    operation_id="get_app_company_list_refresh",
    summary="Read the status of an exchange-catalog refresh",
)
def company_list_refresh_status(request: HttpRequest, task_id: str):
    """Return only the status of this tracked company-catalog refresh."""
    run = get_object_or_404(
        TaskRun,
        task_id=task_id,
        label=COMPANY_LIST_REFRESH_JOB.run_label,
    )
    return {"status": run.status}


@router.post(
    "/company-catalog/refresh",
    response={202: dict, **ERRORS_WITH_VALIDATION},
    auth=OpsSession(),
    operation_id="refresh_app_company_list",
    summary="Queue a refresh of the NSE/BSE company catalog",
)
def refresh_company_list(request: HttpRequest):
    """Queue the tracked exchange-catalog refresh for staff."""
    try:
        run = start_job(COMPANY_LIST_REFRESH_JOB, request.user, request=request)
    except JobBusyError:
        run = active_run(COMPANY_LIST_REFRESH_JOB)
        if run is None:
            raise ApiError(
                "server_error", "The company list update could not be started."
            ) from None
    except JobDispatchError as exc:
        raise ApiError("server_error", str(exc)) from exc
    return Status(202, {"task_id": run.task_id})
