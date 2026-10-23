"""Private IPO previews using the existing query, fact, and score-formatting helpers."""

from django.core.paginator import Paginator
from django.db.models import FloatField
from django.db.models.functions import Cast, NullIf
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Query, Router

from apps.api.v1.common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.ipos.models import Ipo
from apps.reports.formatting import score_out_of_ten
from apps.siteconfig import conf
from apps.web.queries import CATEGORY_FILTERS, IPO_TABS, VERDICT_FILTERS, ipo_facts, ipo_queryset
from apps.web.templatetags.web_extras import rupees, signed, times

from .auth import AppSession
from .schemas import IpoDetail, IpoPage, IpoSummary
from .tables import TableFilters, ordered

router = Router(tags=["IPOs"], auth=AppSession("ipos"))


class IpoFilters(TableFilters):
    """Bound IPO search and validate the filters supported by the existing pages."""

    q: str = Field(default="", max_length=100, description="IPO name search text.")
    status: str = Field(
        default="",
        pattern="^(|open|upcoming|closed|listed|all)$",
        description="Issue status; empty means Active (not listed).",
    )
    verdict: str = Field(
        default="",
        pattern="^(|good|mixed|weak|unknown)$",
        description="Verdict, or all.",
    )
    category: str = Field(
        default="",
        pattern="^(|mainboard|sme)$",
        description="Board, or all.",
    )
    sort: str = Field(
        default="",
        pattern="^(|-?(name|category|status|dates|price_band|gmp|subscribed|listing_gain|score|verdict))$",
    )


def summary(ipo: Ipo) -> IpoSummary:
    """Format an IPO without duplicating score and currency rules in the browser.

    Args:
        ipo: Saved issue to display.

    Returns:
        The same values shown in the existing IPO table.
    """
    dates = str(ipo.open_date.day) + ipo.open_date.strftime(" %b") if ipo.open_date else "–"
    if ipo.open_date and ipo.close_date:
        dates += f" to {ipo.close_date.day}" + ipo.close_date.strftime(" %b")
    return IpoSummary(
        id=ipo.pk,
        name=ipo.name,
        category=ipo.get_category_display(),  # ty: ignore[unresolved-attribute]
        status=ipo.get_status_display().lower(),  # ty: ignore[unresolved-attribute]
        dates=dates,
        price_band=rupees(ipo.price_band_high) if ipo.price_band_high else "–",
        gmp=f"{signed(ipo.gmp_pct)}%" if ipo.gmp_pct is not None else "–",
        subscribed=times(ipo.subscription_times),
        listing_gain=f"{signed(ipo.listing_gain_pct)}%"
        if ipo.listing_gain_pct is not None
        else "–",
        verdict=ipo.verdict or "unknown",
        score=score_out_of_ten(ipo.score, signed=True) if ipo.score is not None else None,
    )


@router.get(
    "/ipos",
    response={200: IpoPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_ipos",
    summary="Search and filter IPOs for the browser",
)
def list_ipos(request: HttpRequest, filters: Query[IpoFilters]):
    """Preserve Active ordering, listed history, board and verdict filtering."""
    values = filters.model_dump(exclude={"page", "page_size", "sort"})
    values["q"] = values["q"].strip()
    rows = ipo_queryset(values).defer("score_inputs")
    if filters.sort.removeprefix("-") == "gmp":
        rows = rows.alias(
            gmp_percentage=Cast("gmp", FloatField())
            * 100.0
            / NullIf(Cast("price_band_high", FloatField()), 0.0)
        )
    rows = ordered(
        rows,
        filters.sort,
        {
            "name": "name",
            "category": "category",
            "status": "status",
            "dates": "open_date",
            "price_band": "price_band_high",
            "gmp": "gmp_percentage",
            "subscribed": "subscription_times",
            "listing_gain": "listing_gain_pct",
            "score": "score",
            "verdict": "verdict",
        },
    )
    page = Paginator(rows, filters.page_size or conf.WEB_PAGE_SIZE).get_page(max(1, filters.page))
    return {
        "items": [summary(ipo) for ipo in page.object_list],
        "page": page.number,
        "pages": page.paginator.num_pages,
        "total": page.paginator.count,
        "page_size": page.paginator.per_page,
        "statuses": [{"value": key, "label": label} for key, label in IPO_TABS.items()],
        "verdicts": [{"value": key, "label": label} for key, label in VERDICT_FILTERS.items()],
        "categories": [{"value": key, "label": label} for key, label in CATEGORY_FILTERS.items()],
    }


@router.get(
    "/ipos/{pk}",
    response={200: IpoDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_app_ipo",
    summary="Read an IPO's facts and verdict evidence",
)
def get_ipo(request: HttpRequest, pk: int):
    """Use saved scoring evidence, preserve units and freshness, and never recalculate scores."""
    ipo = get_object_or_404(Ipo, pk=pk)
    inputs = ipo.score_inputs or {}
    signals = []
    for signal in inputs.get("signals", []):
        name = signal["name"]
        value = signal.get("value")
        signals.append(
            {
                "name": "GMP"
                if name == "gmp"
                else "Subscription"
                if name == "subscription"
                else "News",
                "value": f"{signed(value)}%"
                if name == "gmp"
                else times(value)
                if name == "subscription"
                else score_out_of_ten(value, signed=True),
                "signal": score_out_of_ten(signal.get("signal"), signed=True),
            }
        )
    return {
        **summary(ipo).model_dump(),
        "facts": [
            {"label": label, "value": value} for label, value in ipo_facts(ipo, timezone.now())
        ],
        "signals": signals,
        "notes": inputs.get("notes", []),
        "scored_at": ipo.scored_at,
        "source_url": ipo.source_url,
        "upstox_data": ipo.upstox_data,
        "upstox_updated_at": ipo.upstox_updated_at,
    }
