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
    """Write after commit so clients never refetch uncommitted data."""

    def write() -> None:
        try:
            LiveEvent.objects.create(scope=scope, staff_only=staff_only, payload=payload or {})
        except DatabaseError:
            logger.exception("Could not publish live UI change for %s.", scope)

    transaction.on_commit(write)


@receiver(post_save)
@receiver(post_delete)
def model_changed(sender: type[Model], instance: Model, **kwargs) -> None:
    """Invalidate affected pages, and announce task state without exposing output."""
    if kwargs.get("raw"):
        return
    scope = SCOPES.get(sender._meta.app_label)
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
    """Refresh linked news and permission changes after relationship edits."""
    if action in {"post_add", "post_remove", "post_clear"}:
        scope = SCOPES.get(instance._meta.app_label)
        if scope:
            publish(scope, staff_only=scope == "ops")


def frame(event: str, payload: dict, cursor: int) -> str:
    """Encode one SSE frame; JSON escaping prevents newline injection."""
    return f"id: {cursor}\nevent: {event}\ndata: {json.dumps(payload)}\n\n"


def event_stream(cursor: int, *, staff: bool):
    """Stream bounded batches, heartbeat on idle, and let EventSource resume on reconnect."""
    yield "retry: 1000\n\n"
    yield frame("ready", {}, cursor)
    deadline = time.monotonic() + STREAM_SECONDS
    idle_ticks = 0
    while time.monotonic() < deadline:
        events = LiveEvent.objects.filter(pk__gt=cursor).order_by("pk")
        if not staff:
            events = events.filter(staff_only=False)
        batch = list(events[:200])
        for event in batch:
            cursor = event.pk
            yield frame("change", {"scope": event.scope, **event.payload}, cursor)
        if len(batch) < 200:  # noqa: PLR2004
            if idle_ticks % 5 == 0:
                yield "event: refresh\ndata: {}\n\n"
            yield ": heartbeat\n\n"
            time.sleep(1)
            idle_ticks += 1
    yield frame("reconnect", {}, cursor)


@login_not_required
def events(request: HttpRequest, *, staff: bool = False):
    """Authenticate every bounded connection, preserving API errors instead of redirects."""
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
    response = StreamingHttpResponse(
        event_stream(cursor, staff=staff), content_type="text/event-stream"
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Accel-Buffering"] = "no"
    return response


@login_not_required
def staff_events(request: HttpRequest):
    """Keep staff events under the proxy's Ops IP allowlist."""
    return events(request, staff=True)
