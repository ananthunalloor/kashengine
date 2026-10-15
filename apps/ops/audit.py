"""The audit trail: who did what on the Ops pages.

The module has one function, `record`. The views and the job code call it after an admin action,
for example "run job" in `jobs.start_job`. Each call saves one `AuditEvent` row. The prune task
(`ops.prune`) deletes old rows. The audit page shows them.
"""

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
    """Save one audit event and return it.

    The function copies the user name into `actor_name`. The row keeps the name after the user is
    deleted. The function writes at once. It does not wait for a transaction to finish.

    Args:
        actor: The user who did the action. The function reads the name with `get_username()`.
        action: A short name for the action, for example `run job`. The model allows 50 characters.
        target: What the action changed, for example a job label. The function cuts it to 200
            characters. The default is an empty text.
        detail: Extra text for the audit page. It is not cut. The default is an empty text.
        request: The web request of the action. The function saves the client address from it.
            With `None`, the address is `None`.

    Returns:
        The saved `AuditEvent`.

    Side effects:
        Writes one row to the `AuditEvent` table.
    """
    return AuditEvent.objects.create(
        actor=actor,
        actor_name=actor.get_username(),
        action=action,
        target=target[:200],
        detail=detail,
        ip_address=client_ip(request),
    )
