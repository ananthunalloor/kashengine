"""Daily reports: `/api/v1/reports`."""

from datetime import date

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Query, Router

from apps.reports.models import Report

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from .schemas import ReportDetail, ReportPage

router = Router(tags=["Reports"], auth=for_feature("reports"))


@router.get(
    "/reports",
    response={200: ReportPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_reports",
    summary="List daily reports",
)
def list_reports(request: HttpRequest, params: Query[PageParams]):
    """List the daily reports, newest first.

    There is one report for each date. The list has no report text. Read one report to get it.

    **Required feature:** `reports`.
    """
    return paginate(Report.objects.all(), params)


@router.get(
    "/reports/{day}",
    response={200: ReportDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_report",
    summary="Get one daily report",
)
def get_report(request: HttpRequest, day: date):
    """Return the report of one date, with its full text and its data.

    The `day` is a date like `2026-10-07`. The answer is `404` if no report exists for it.

    **Required feature:** `reports`.
    """
    return get_object_or_404(Report, date=day)
