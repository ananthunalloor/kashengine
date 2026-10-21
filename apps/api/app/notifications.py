"""Short-lived SSE responses for staff task-run notifications."""

import json

from django.contrib.auth.decorators import login_not_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.ops.models import TaskRun


def _cursor(finished_at, run_id: int) -> str:
    return f"{finished_at.isoformat()}|{run_id}"


@login_not_required
def notifications(request: HttpRequest) -> HttpResponse:
    """Return finished task runs since the browser's last SSE cursor.

    Responses end immediately so the synchronous WSGI workers are not held by open streams;
    EventSource reconnects automatically and supplies the last event ID.
    """
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return HttpResponse(status=401)
    if not user.is_staff:
        return HttpResponse(status=204)

    cursor = request.headers.get("Last-Event-ID", "")
    try:
        raw_time, raw_id = cursor.rsplit("|", 1)
        cursor_time = parse_datetime(raw_time)
        cursor_id = int(raw_id)
        if cursor_time is None or timezone.is_naive(cursor_time):
            raise ValueError
    except (ValueError, TypeError):
        latest = (
            TaskRun.objects.filter(finished_at__isnull=False)
            .order_by("-finished_at", "-pk")
            .first()
        )
        cursor_time = latest.finished_at if latest else timezone.now()
        cursor_id = latest.pk if latest else 0
        cursor = _cursor(cursor_time, cursor_id)
        body = f"retry: 1500\nid: {cursor}\n\n"
    else:
        runs = (
            TaskRun.objects.filter(
                finished_at__isnull=False,
                status__in=(TaskRun.Status.SUCCESS, TaskRun.Status.FAILURE),
            )
            .filter(Q(finished_at__gt=cursor_time) | Q(finished_at=cursor_time, pk__gt=cursor_id))
            .order_by("finished_at", "pk")[:50]
        )
        events = []
        for run in runs:
            error = next((line.strip() for line in run.error.splitlines() if line.strip()), "")
            data = {
                "run_id": run.pk,
                "label": run.label,
                "status": run.status,
                "error": error[:300],
                "url": f"/ops/runs/{run.pk}/",
            }
            events.append(
                f"id: {_cursor(run.finished_at, run.pk)}\n"
                f"event: job\n"
                f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
            )
        body = "retry: 1500\n\n" + "".join(events)

    response = HttpResponse(body, content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache, no-store"
    response["X-Accel-Buffering"] = "no"
    return response
