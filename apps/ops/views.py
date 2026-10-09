"""The Ops pages. Staff users can look. Superusers can also change things (POST requests)."""

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.markets.evaluation import accuracy_stats
from apps.web.datastar import is_datastar, querystring, read_filters, read_page, signals_json

from . import audit, configview, health, jobs, logs, metrics, schedule, users
from .models import AuditEvent, LoginEvent, TaskRun
from .permissions import staff_required, superuser_post_required

RUN_STATUS_FILTERS = TaskRun.Status.choices
RUN_TRIGGER_FILTERS = TaskRun.Trigger.choices
RECENT_RUNS = 8
RECENT_LOGINS = 6
LOG_FILTERS = ("level", "logger", "q", "limit", "live")
RUN_FILTERS = ("label", "status", "trigger", "page")
LOGIN_FILTERS = ("kind", "q", "hours", "page")
USER_FILTERS = ("q",)
LOGIN_HOURS = {"24": "Last 24 hours", "168": "Last 7 days", "720": "Last 30 days", "": "All"}


def _paginate(items, filters: dict[str, str]):
    return Paginator(items, settings.OPS_PAGE_SIZE).get_page(read_page(filters))


@staff_required
def overview(request: HttpRequest) -> HttpResponse:
    """The health of the system. A Datastar request gets only the live panel."""
    refresh = request.GET.get("refresh") == "1"
    results = health.run_all(use_cache=not refresh)
    now = timezone.now()
    context = {
        "groups": results,
        "overall": health.overall(results),
        "checked_at": now,
        "running": TaskRun.objects.filter(
            status__in=[TaskRun.Status.PENDING, TaskRun.Status.STARTED]
        ).order_by("-created_at")[:RECENT_RUNS],
        "recent_runs": TaskRun.objects.order_by("-created_at")[:RECENT_RUNS],
        "failed_logins": users.failed_logins_by_address(limit=RECENT_LOGINS),
        "session_count": len({s.user_id for s in users.active_sessions()}),
        "section": "overview",
    }
    template = "ops/_health_panel.html" if is_datastar(request) else "ops/overview.html"
    return render(request, template, context)


def _job_rows() -> list[dict]:
    """One row for each job: its last run, its schedule, and its numbers of the last 7 days."""
    stats = {row["label"]: row for row in metrics.task_stats(days=7)}
    now = timezone.now()
    rows = []
    for job in jobs.JOBS:
        last = TaskRun.objects.filter(label=job.run_label).order_by("-created_at").first()
        entries = schedule.entries_for(job.target) if job.kind == jobs.TASK else []
        rows.append(
            {
                "job": job,
                "last": last,
                "active": jobs.active_run(job),
                "stats": stats.get(job.run_label),
                "schedules": [entry.cron_text for entry in entries],
                "next_run": schedule.next_run(job.target, now) if entries else None,
            }
        )
    return rows


@staff_required
def job_list(request: HttpRequest) -> HttpResponse:
    """All jobs with the time of the last run, the next run, and the run buttons."""
    grouped: dict[str, list[dict]] = {}
    for row in _job_rows():
        grouped.setdefault(row["job"].group, []).append(row)
    return render(request, "ops/jobs.html", {"groups": grouped, "section": "jobs"})


@superuser_post_required
def job_run(request: HttpRequest, key: str) -> HttpResponse:
    """Start a job. A job with a warning needs a confirmation."""
    job = jobs.JOBS_BY_KEY.get(key)
    if job is None:
        raise Http404
    if job.confirm and request.POST.get("confirm") != "yes":
        messages.error(request, f"Tick the box to confirm. {job.confirm}")
        return redirect("ops:jobs")
    try:
        run = jobs.start_job(job, request.user, request)
    except jobs.JobBusyError as exc:
        messages.warning(request, str(exc))
        return redirect("ops:jobs")
    except jobs.JobDispatchError as exc:
        messages.error(request, str(exc))
        return redirect("ops:jobs")
    messages.success(request, f"Started: {job.label}.")
    return redirect("ops:run", pk=run.pk)


@staff_required
def run_list(request: HttpRequest) -> HttpResponse:
    """The history of all runs, with filters."""
    filters = read_filters(request, RUN_FILTERS)
    runs = TaskRun.objects.select_related("triggered_by")
    if filters["label"]:
        runs = runs.filter(label=filters["label"])
    if filters["status"] in TaskRun.Status.values:
        runs = runs.filter(status=filters["status"])
    if filters["trigger"] in TaskRun.Trigger.values:
        runs = runs.filter(trigger=filters["trigger"])
    context = {
        "filters": filters,
        "page": _paginate(runs, filters),
        "qs": querystring(filters),
        "labels": TaskRun.objects.order_by("label").values_list("label", flat=True).distinct(),
        "statuses": RUN_STATUS_FILTERS,
        "OPS_RETENTION_DAYS": settings.OPS_RETENTION_DAYS,
        "triggers": RUN_TRIGGER_FILTERS,
        "section": "runs",
    }
    return render(request, "ops/runs.html", context)


@staff_required
def run_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """One run with its result, its error, and its output. It refreshes while the run is active."""
    run = get_object_or_404(TaskRun.objects.select_related("triggered_by"), pk=pk)
    template = "ops/_run_panel.html" if is_datastar(request) else "ops/run_detail.html"
    return render(request, template, {"run": run, "section": "runs"})


@staff_required
def log_view(request: HttpRequest) -> HttpResponse:
    """The log file, newest first, with filters. A Datastar request gets only the entries."""
    filters = read_filters(request, LOG_FILTERS)
    view = logs.query(
        level=filters["level"],
        logger_name=filters["logger"],
        text=filters["q"],
        limit=logs.clean_limit(filters["limit"]),
    )
    context = {
        "view": view,
        "filters": filters,
        "signals": signals_json(filters),
        "levels": logs.LEVELS,
        "live": filters["live"].lower() == "true",
        "section": "logs",
    }
    template = "ops/_log_panel.html" if is_datastar(request) else "ops/logs.html"
    return render(request, template, context)


@staff_required
def metric_view(request: HttpRequest) -> HttpResponse:
    """Numbers about the host, the queue, the database, the jobs, and the data."""
    context = {
        "tasks": metrics.task_stats(days=7),
        "charts": metrics.charts(),
        "tables": metrics.table_counts(),
        "db_size": metrics.format_bytes(metrics.database_size()),
        "host": metrics.host_stats(),
        "redis": metrics.redis_stats(),
        "workers": metrics.worker_stats(),
        "llm": metrics.llm_stats(),
        "accuracy": accuracy_stats(),
        "section": "metrics",
    }
    return render(request, "ops/metrics.html", context)


@staff_required
def user_list(request: HttpRequest) -> HttpResponse:
    """All users with their last login, their login count, and their sessions."""
    filters = read_filters(request, USER_FILTERS)
    sessions: dict[int, int] = {}
    for session in users.active_sessions():
        sessions[session.user_id] = sessions.get(session.user_id, 0) + 1
    rows = [
        {"user": user, "sessions": sessions.get(user.pk, 0)}
        for user in users.users_with_stats(filters["q"])
    ]
    context = {"rows": rows, "filters": filters, "section": "users"}
    return render(request, "ops/users.html", context)


@staff_required
def user_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """One user: details, sessions, login events, and admin site actions."""
    user = get_object_or_404(get_user_model(), pk=pk)
    context = {
        "subject": user,
        "sessions": users.sessions_of(user.pk),
        "current_key": request.session.session_key or "",
        "events": LoginEvent.objects.filter(user=user)[:30],
        "failed": LoginEvent.objects.filter(
            kind=LoginEvent.Kind.FAILED, username=user.get_username()
        )[:10],
        "admin_actions": LogEntry.objects.filter(user=user).select_related("content_type")[:15],
        "ops_actions": AuditEvent.objects.filter(actor=user)[:15],
        "runs": TaskRun.objects.filter(triggered_by=user)[:10],
        "section": "users",
    }
    return render(request, "ops/user_detail.html", context)


@superuser_post_required
def user_end_sessions(request: HttpRequest, pk: int) -> HttpResponse:
    """End one session (with `key`) or all sessions of a user."""
    user = get_object_or_404(get_user_model(), pk=pk)
    current = request.session.session_key or ""
    key = request.POST.get("key", "")
    try:
        if key:
            if key not in {s.key for s in users.sessions_of(user.pk)}:
                raise Http404
            count = users.end_session(key, current_key=current)
        else:
            count = users.end_user_sessions(user.pk, current_key=current)
    except users.UserActionError as exc:
        messages.error(request, str(exc))
        return redirect("ops:user", pk=pk)
    audit.record(request.user, "end sessions", user.get_username(), f"{count} ended", request)
    messages.success(request, f"Ended {count} session(s) of {user.get_username()}.")
    return redirect("ops:user", pk=pk)


@superuser_post_required
def user_set_active(request: HttpRequest, pk: int) -> HttpResponse:
    """Turn a user on or off. A user that is off cannot log in."""
    user = get_object_or_404(get_user_model(), pk=pk)
    active = request.POST.get("active") == "yes"
    try:
        users.set_user_active(user, active, acting_user=request.user)
    except users.UserActionError as exc:
        messages.error(request, str(exc))
        return redirect("ops:user", pk=pk)
    audit.record(
        request.user,
        "turn on user" if active else "turn off user",
        user.get_username(),
        "",
        request,
    )
    state = "on" if active else "off"
    messages.success(request, f"{user.get_username()} is now {state}.")
    return redirect("ops:user", pk=pk)


@staff_required
def login_list(request: HttpRequest) -> HttpResponse:
    """All logins, logouts, and failed logins, with the addresses that fail most."""
    filters = read_filters(request, LOGIN_FILTERS)
    hours = int(filters["hours"]) if filters["hours"] in LOGIN_HOURS and filters["hours"] else None
    events = users.login_events(filters["kind"], filters["q"], hours)
    context = {
        "filters": filters,
        "page": _paginate(events, filters),
        "qs": querystring(filters),
        "kinds": LoginEvent.Kind.choices,
        "hours_choices": LOGIN_HOURS,
        "failed_by_address": users.failed_logins_by_address(),
        "section": "logins",
    }
    return render(request, "ops/logins.html", context)


@staff_required
def audit_list(request: HttpRequest) -> HttpResponse:
    """What admins did on the Ops pages."""
    filters = read_filters(request, ("page",))
    context = {
        "page": _paginate(AuditEvent.objects.select_related("actor"), filters),
        "qs": "",
        "section": "audit",
    }
    return render(request, "ops/audit.html", context)


@staff_required
def config_view(request: HttpRequest) -> HttpResponse:
    """The settings, with the secrets hidden."""
    return render(
        request,
        "ops/config.html",
        {"sections": configview.sections(), "section": "config", "now": timezone.now()},
    )
