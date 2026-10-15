"""IPOs: `/api/v1/ipos`."""

from typing import Literal

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, Query, Router

from apps.ipos.models import Ipo
from apps.web import queries

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION, MAX_SEARCH_CHARS
from .schemas import IpoCategory, IpoDetail, IpoPage, IpoVerdict

router = Router(tags=["IPOs"], auth=for_feature("ipos"))


class IpoFilters(PageParams):
    """Filters for the IPO list. All filters are optional and they combine with AND."""

    q: str | None = Field(None, max_length=MAX_SEARCH_CHARS, description="Text in the name.")
    status: Literal["active", "open", "upcoming", "closed", "listed", "all"] = Field(
        "all",
        description="`active` means open and upcoming first, then closed, without listed IPOs. "
        "`all` is the default.",
    )
    verdict: IpoVerdict | None = Field(None, description="Only IPOs with this verdict.")
    category: IpoCategory | None = Field(None, description="Mainboard or SME.")


@router.get(
    "/ipos",
    response={200: IpoPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_ipos",
    summary="List IPOs",
)
def list_ipos(request: HttpRequest, filters: Query[IpoFilters]):
    """List IPOs with their dates, price band, GMP, subscription and score.

    The score and the verdict come from the scoring step. An IPO without enough data has the
    verdict `unknown`. This is an analysis aid and not investment advice.

    **Required feature:** `ipos`.
    """
    tab = "" if filters.status == "active" else filters.status
    ipos = queries.ipo_queryset(
        {
            "q": filters.q or "",
            "status": tab,
            "verdict": filters.verdict or "",
            "category": filters.category or "",
        }
    ).select_related("company")
    return paginate(ipos, filters)


@router.get(
    "/ipos/{ipo_id}",
    response={200: IpoDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_ipo",
    summary="Get one IPO",
)
def get_ipo(request: HttpRequest, ipo_id: int):
    """Return one IPO with the inputs of its score.

    `signals` lists each input that the score used. `notes` says why an input was left out.
    The answer is `404` if the IPO does not exist.

    **Required feature:** `ipos`.
    """
    return get_object_or_404(Ipo.objects.select_related("company"), pk=ipo_id)
