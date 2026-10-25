"""Replayable server-sent events containing invalidations, never business data or secrets."""

# Django exposes model metadata through its documented _meta API.
# ruff: noqa: SLF001

import json
import logging
import time

from django.contrib.auth.decorators import login_not_required
from django.db import DatabaseError, transaction
from django.db.models import Model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver
from django.http import HttpRequest, StreamingHttpResponse

from apps.api.app.auth import AppSession, OpsSession
from apps.api.errors import ApiError, problem

from .models import LiveEvent

logger = logging.getLogger(__name__)
STREAM_SECONDS = 20
SCOPES = {
    "news": "news",
    "companies": "companies",
    "markets": "markets",
    "ipos": "ipos",
    "reports": "reports",
    "delivery": "delivery",
    "ops": "ops",
    "access": "account",
    "auth": "account",
    "siteconfig": "session",
    "django_celery_beat": "ops",
}


def publish(scope: str, *, staff_only: bool = False, payload: dict | None = None) -> None:
    """Queue one live event. The event is written after the transaction commits.

    A client that refetches after the event must never see uncommitted data. So the write waits
    for `transaction.on_commit`. If the transaction rolls back, nothing is published. If the
    write fails, the error is logged and the caller is not told.

    Args:
        scope: The page group that must refresh, for example `news`, `ops` or `all`.
        staff_only: If true, only the Ops stream sends the event.
        payload: Small safe data for the client, for example a run id and status. It must never
            contain business data or secrets. The default is an empty dict.
    """

    def write() -> None:
        """Save the event row. A database error is logged and then ignored."""
        try:
            LiveEvent.objects.create(scope=scope, staff_only=staff_only, payload=payload or {})
        except DatabaseError:
            logger.exception("Could not publish live UI change for %s.", scope)

    transaction.on_commit(write)


@receiver(post_save)
@receiver(post_delete)
def model_changed(sender: type[Model], instance: Model, **kwargs) -> None:
    """Publish a live event when a saved or deleted row changes a page.

    The app label of the model gives the scope (`SCOPES`). A `TaskRun` save also sends the id,
    label and status of the run, but never its output. A finished run sends an extra `all`
    event. A model with no scope sends nothing. A fixture load (`raw`) sends nothing.

    Args:
        sender: The model class that sent the signal.
        instance: The row that was saved or deleted.
        **kwargs: Other signal arguments. The code reads `raw` and `signal`.
    """
    if kwargs.get("raw"):
        return
    scope = SCOPES.get(sender._meta.app_label)
    if sender._meta.label_lower == "markets.tradingcalendarday":
        scope = "session"
    if sender._meta.label_lower == "api.apitoken":
        scope = "account"
    if scope is None:
        return
    payload = {}
    from apps.ops.models import TaskRun  # noqa: PLC0415

    if isinstance(instance, TaskRun) and kwargs.get("signal") is post_save:
        payload = {"run": {"id": instance.pk, "label": instance.label, "status": instance.status}}
        if instance.status in {TaskRun.Status.SUCCESS, TaskRun.Status.FAILURE}:
            publish("all")
    publish(scope, staff_only=scope == "ops", payload=payload)


@receiver(m2m_changed)
def relationships_changed(sender, instance, action, **kwargs) -> None:
    """Publish a live event after a many-to-many change, for example linked news or permissions.

    Args:
        sender: The through model of the relationship.
        instance: The row whose relationship changed.
        action: The signal action. Only `post_add`, `post_remove` and `post_clear` publish.
        **kwargs: Other signal arguments. The code ignores them.
    """
    if action in {"post_add", "post_remove", "post_clear"}:
        scope = SCOPES.get(instance._meta.app_label)
        if scope:
            publish(scope, staff_only=scope == "ops")


def frame(event: str, payload: dict, cursor: int) -> str:
    """Encode one server-sent event (SSE) frame.

    `json.dumps` escapes new lines in the payload, so a payload cannot add a field to the frame.

    Args:
        event: The event name, for example `ready`, `change` or `reconnect`.
        payload: The data of the event. It must be JSON-serializable.
        cursor: The id of the last event that the frame covers. The browser sends it back as
            `Last-Event-ID` when it reconnects.

    Returns:
        The text of one frame that ends with a blank line.
    """
    return f"id: {cursor}\nevent: {event}\ndata: {json.dumps(payload)}\n\n"


def event_stream(cursor: int, *, staff: bool, resync: bool = True):
    """Stream the live events for about `STREAM_SECONDS` seconds, then ask the client to reconnect.

    The stream sends a `ready` frame first. It then polls the database each second, sends up to
    200 new events in each batch, and sends a heartbeat comment when the batch is not full. At
    the end it sends a `reconnect` frame. The browser `EventSource` then reconnects with
    `Last-Event-ID`.

    Args:
        cursor: The id of the last event that the client has seen. Only newer events are sent.
        staff: If true, the stream includes the staff-only events.
        resync: If true, the `ready` frame tells the client to refetch all data, because the
            cursor is missing or too old.

    Yields:
        Text frames in the SSE format.
    """
    yield "retry: 1000\n\n"
    yield frame("ready", {"resync": resync}, cursor)
    deadline = time.monotonic() + STREAM_SECONDS
    while time.monotonic() < deadline:
        events = LiveEvent.objects.filter(pk__gt=cursor).order_by("pk")
        if not staff:
            events = events.filter(staff_only=False)
        batch = list(events[:200])
        for event in batch:
            cursor = event.pk
            yield frame("change", {"scope": event.scope, **event.payload}, cursor)
        if len(batch) < 200:  # noqa: PLR2004
            yield ": heartbeat\n\n"
            time.sleep(1)
    yield frame("reconnect", {}, cursor)


@login_not_required
def events(request: HttpRequest, *, staff: bool = False):
    """Open a live-update stream for a signed-in user.

    Each connection is authenticated again, so a sign-out or a role change takes effect at the
    next reconnect. The view returns problem+json errors and never a login redirect. A cursor
    that is missing, ahead of the newest event, or older than the oldest saved event gives a
    `resync` stream that starts at the newest event.

    Args:
        request: The HTTP request. Only `GET` is allowed. The optional `Last-Event-ID` header
            is the cursor.
        staff: If true, the user must pass the Ops session check and the stream includes
            staff-only events.

    Returns:
        A `text/event-stream` response with `Cache-Control: private, no-store`. For a bad method,
        a bad cursor or a failed check it returns a problem+json error instead.
    """
    if request.method != "GET":
        return problem(request, "validation_error", "Use GET for live updates.")
    try:
        auth = OpsSession() if staff else AppSession()
        if auth.authenticate(request, request.COOKIES.get(auth.param_name)) is None:
            return problem(request, "unauthenticated", "Sign in to continue.")
    except ApiError as exc:
        return problem(request, exc.code, exc.detail, headers=exc.headers)
    latest = LiveEvent.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
    raw = request.headers.get("Last-Event-ID", "")
    if raw and (not raw.isascii() or not raw.isdecimal() or len(raw) > 19):  # noqa: PLR2004
        return problem(request, "validation_error", "Invalid live event cursor.")
    cursor = min(int(raw), latest) if raw else latest
    oldest = LiveEvent.objects.order_by("pk").values_list("pk", flat=True).first() or 0
    resync = not raw or int(raw) > latest or cursor < oldest - 1
    if resync:
        cursor = latest
    response = StreamingHttpResponse(
        event_stream(cursor, staff=staff, resync=resync), content_type="text/event-stream"
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Accel-Buffering"] = "no"
    return response


@login_not_required
def staff_events(request: HttpRequest):
    """Open the staff live-update stream at a path that the Ops IP allowlist covers.

    Args:
        request: The HTTP request. See `events`.

    Returns:
        The response of `events` with `staff=True`.
    """
    return events(request, staff=True)
