"""Private read-only delivery preview, with recipients excluded and diagnostics staff-only."""

from django.http import HttpRequest
from ninja import Router

from apps.api.v1.common import ERRORS
from apps.delivery.service import configured_chat_ids
from apps.web.queries import latest_deliveries

from .auth import AppSession
from .schemas import DeliveryPage

router = Router(tags=["Delivery"], auth=AppSession("delivery"))


@router.get(
    "/delivery",
    response={200: DeliveryPage, **ERRORS},
    operation_id="get_app_delivery",
    summary="Read the latest delivery attempts",
)
def get_delivery(request: HttpRequest):
    """Expose the same latest attempts as the web page, without recipient identifiers."""
    staff = getattr(request.user, "is_staff", False)
    return {
        "chat_count": len(configured_chat_ids()),
        "items": [
            {
                "id": log.pk,
                "channel": log.get_channel_display(),  # ty: ignore[unresolved-attribute]
                "status": log.status,
                "status_label": log.get_status_display(),  # ty: ignore[unresolved-attribute]
                "created_at": log.created_at,
                "error": log.error if staff else None,
                "report_date": log.report.date if log.report else None,
            }
            for log in latest_deliveries()
        ],
    }
