"""Private Reports presentation API; the public v1 contract is unchanged."""

from datetime import date

from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.v1.common import ERRORS_WITH_NOT_FOUND, ERRORS_WITH_VALIDATION
from apps.delivery.models import DeliveryLog
from apps.reports.builder import render_text
from apps.reports.formatting import score_out_of_ten
from apps.reports.models import Report
from apps.siteconfig import conf

from .auth import AppSession
from .schemas import ReportDetail, ReportPage, ReportSummary

router = Router(tags=["Reports"], auth=AppSession("reports"))


def summary(report: Report) -> ReportSummary:
    """Use the same display scale as the existing Reports templates.

    Args:
        report: The saved report whose outlook is being displayed.

    Returns:
        Its date, direction, and formatted signal strength.
    """
    return ReportSummary(
        date=report.date,
        prediction=report.prediction,
        strength=score_out_of_ten(report.confidence) if report.confidence is not None else None,
    )


@router.get(
    "/reports",
    response={200: ReportPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_app_reports",
    summary="List daily reports for the browser",
)
def list_reports(request: HttpRequest, page: int = 1):
    """Return a bounded page using the existing web page size and date ordering."""
    result = Paginator(Report.objects.defer("text", "data"), conf.WEB_PAGE_SIZE).get_page(
        max(1, page)
    )
    return {
        "items": [summary(report) for report in result.object_list],
        "page": result.number,
        "pages": result.paginator.num_pages,
        "total": result.paginator.count,
    }


@router.get(
    "/reports/{day}",
    response={200: ReportDetail, **ERRORS_WITH_NOT_FOUND},
    operation_id="get_app_report",
    summary="Read a report and its delivery status",
)
def get_report(request: HttpRequest, day: date):
    """Preserve saved-data rendering, adjacent dates, and staff-only delivery diagnostics."""
    report = get_object_or_404(Report, date=day)
    return {
        **summary(report).model_dump(),
        "text": render_text(report.data) if report.data else report.text,
        "older": Report.objects.filter(date__lt=day)
        .order_by("-date")
        .values_list("date", flat=True)
        .first(),
        "newer": Report.objects.filter(date__gt=day)
        .order_by("date")
        .values_list("date", flat=True)
        .first(),
        "deliveries": [
            {
                "id": delivery.pk,
                "channel": delivery.get_channel_display(),  # ty: ignore[unresolved-attribute]
                "status": delivery.status,
                "status_label": delivery.get_status_display(),  # ty: ignore[unresolved-attribute]
                "created_at": delivery.created_at,
                "error": delivery.error if getattr(request.user, "is_staff", False) else None,
            }
            for delivery in DeliveryLog.objects.filter(report=report)
        ],
    }
