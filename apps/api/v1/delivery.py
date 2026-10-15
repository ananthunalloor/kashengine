"""Delivery log: `/api/v1/delivery/logs`."""

from django.http import HttpRequest
from ninja import Query, Router

from apps.delivery.models import DeliveryLog

from ..auth import for_feature
from ..pagination import PageParams, paginate
from .common import ERRORS_WITH_VALIDATION
from .schemas import DeliveryPage

router = Router(tags=["Delivery"], auth=for_feature("delivery"))

VISIBLE_RECIPIENT_CHARS = 4


def mask(recipient: str) -> str:
    """Hide all but the last four characters of a chat id or an address.

    Args:
        recipient: The stored recipient.

    Returns:
        `…` followed by the last four characters. A short or empty value gives `…` only.
    """
    if len(recipient) <= VISIBLE_RECIPIENT_CHARS:
        return "…" if recipient else ""
    return "…" + recipient[-VISIBLE_RECIPIENT_CHARS:]


@router.get(
    "/delivery/logs",
    response={200: DeliveryPage, **ERRORS_WITH_VALIDATION},
    operation_id="list_delivery_logs",
    summary="List report delivery attempts",
)
def list_delivery_logs(request: HttpRequest, params: Query[PageParams]):
    """List the attempts to send a report, newest first.

    The recipient is masked. The error text is only for staff users, because it can name an
    internal setting. Other users see the status only.

    **Required feature:** `delivery`.
    """
    is_staff = bool(getattr(request.user, "is_staff", False))

    def convert(log: DeliveryLog) -> dict:
        """Make the answer row of one delivery log. Only staff users see the error text."""
        return {
            "id": log.pk,
            "report_date": log.report.date if log.report else None,
            "channel": log.channel,
            "status": log.status,
            "recipient": mask(log.recipient),
            "error": (log.error or None) if is_staff else None,
            "created_at": log.created_at,
        }

    return paginate(DeliveryLog.objects.select_related("report"), params, convert)
