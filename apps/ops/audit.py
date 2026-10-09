"""The audit trail: who did what on the Ops pages."""

from django.http import HttpRequest

from .models import AuditEvent
from .requestinfo import client_ip


def record(
    actor,
    action: str,
    target: str = "",
    detail: str = "",
    request: HttpRequest | None = None,
) -> AuditEvent:
    """Save one audit event. `actor` is a user."""
    return AuditEvent.objects.create(
        actor=actor,
        actor_name=actor.get_username(),
        action=action,
        target=target[:200],
        detail=detail,
        ip_address=client_ip(request),
    )
