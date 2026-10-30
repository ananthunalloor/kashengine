"""The monitoring and user pages of the Ops area.

Staff users can look at these pages, except for Logs, which is superuser-only. Only a superuser
can change something, and only with a POST request. The decorators in `permissions.py` enforce
these rules. `urls.py` maps each view to a path in the `ops` namespace. The feature permission
and subscription views are in `views_access.py`. The settings, schedule, feed, and instrument
views are in `views_settings.py`.

The module has these groups of views:

- Health and jobs: `overview`, `job_list`, `job_run`, `run_list`, `run_detail`.
- Logs and metrics: `log_view`, `metric_view`, `config_view`.
- Users and logins: `user_list`, `user_detail`, `user_end_sessions`, `user_set_active`,
  `login_list`, `lockout_unlock`.
- Audit trail: `audit_list`.

The data comes from the helper modules `health`, `jobs`, `logs`, `metrics`, `schedule`, `users`,
`audit`, and `configview`. Every view passes a `section` value in its template context. The menu
in `context.py` uses it to mark the open page. A view that changes data writes one row to the
audit trail with `audit.record` and then shows a message with `django.contrib.messages`.

Settings: `OPS_PAGE_SIZE` (rows on a list page) and `OPS_RETENTION_DAYS` (shown on the run list)
come from `apps.siteconfig.conf`.
"""

from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.api import tokens
from apps.api.models import ApiToken
from apps.markets.evaluation import accuracy_stats
from apps.siteconfig import conf
from apps.web.datastar import is_datastar, querystring, read_filters, read_page, signals_json

from . import audit, configview, health, jobs, logs, metrics, schedule, users, views_access
from .models import AuditEvent, LoginEvent, TaskRun
from .permissions import staff_required, superuser_post_required, superuser_required

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
    """Return one page of a queryset or a list.

    The page size is the setting `OPS_PAGE_SIZE`. The page number comes from the `page` filter.
    A bad page number gives page 1. A number that is too large gives the last page.

    Args:
        items: A queryset or a list to split into pages.
        filters: The filter values that `read_filters` made. The key `page` is optional.

    Returns:
        The Django `Page` object for the requested page.
    """
    return Paginator(items, conf.OPS_PAGE_SIZE).get_page(read_page(filters))


@staff_required
def overview(request: HttpRequest) -> HttpResponse:
    """Show the health of the system and the latest task runs.

    The view runs all health checks. The result is cached for a short time, so a quick reload
    does not run the checks again. The query parameter `refresh=1` ignores the cache. A Datastar
    request (the live refresh of the page) gets only the HTML of the health panel.

    The context has the check results, the worst status, the time of the check, the runs that
    wait or run now (newest first, at most `RECENT_RUNS`), the newest runs, the addresses with
    the most failed logins in the last 24 hours (at most `RECENT_LOGINS`), and the number of
    users that have an active session.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/overview.html`, or the panel `ops/_health_panel.html` for Datastar.
    """
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
    return TemplateResponse(request, template, context)


def _job_rows() -> list[dict]:
    """Build one row for each job in the job list.

    A row has the job, its last run, the run that is active now, the numbers of the last 7 days,
    the cron lines of its schedule entries, and the time of its next run. Only a job of the kind
    task can have schedule entries. A job of the kind command always has an empty schedule.

    Returns:
        A list of dictionaries in the order of `jobs.JOBS`. The keys are `job`, `last`, `active`,
        `stats`, `schedules`, and `next_run`. `last`, `active`, `stats`, and `next_run` can be
        `None`.

    Note:
        The function makes some database queries for each job. The list of jobs is short.
    """
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
    """Show all jobs in groups, with the last run, the next run, and the run buttons.

    The jobs are grouped by the `group` field of the job. The groups keep the order of the first
    appearance in `jobs.JOBS`.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/jobs.html`.
    """
    grouped: dict[str, list[dict]] = {}
    for row in _job_rows():
        grouped.setdefault(row["job"].group, []).append(row)
    return TemplateResponse(request, "ops/jobs.html", {"groups": grouped, "section": "jobs"})


@superuser_post_required
def job_run(request: HttpRequest, key: str) -> HttpResponse:
    """Queue a job that an admin chose and return to the jobs page.

    Only a job in the fixed list `jobs.JOBS_BY_KEY` can run. If the job has a `confirm` text, the
    POST field `confirm` must be `yes`. If not, the view shows an error and starts nothing. If the
    same job waits or runs, the view shows a warning. If the queue is down, the view shows an
    error. In these cases the view goes back to the job list.

    Args:
        request: The POST request of a superuser.
        key: The key of the job, from the URL.

    Returns:
        A redirect back to the job list after dispatching the new job, or to the job list on error.

    Raises:
        Http404: If no job has this key.

    Side effects:
        `jobs.start_job` creates a `TaskRun` row, writes the audit event `run job`, and sends a
        Celery task to the queue.
    """
    job = jobs.JOBS_BY_KEY.get(key)
    if job is None:
        raise Http404
    if job.confirm and request.POST.get("confirm") != "yes":
        messages.error(request, f"Tick the box to confirm. {job.confirm}")
        return redirect("ops:jobs")
    try:
        jobs.start_job(job, request.user, request)
    except jobs.JobBusyError as exc:
        messages.warning(request, str(exc))
        return redirect("ops:jobs")
    except jobs.JobDispatchError as exc:
        messages.error(request, str(exc))
        return redirect("ops:jobs")
    messages.success(request, f"Started: {job.label}.")
    return redirect("ops:jobs")


@staff_required
def run_list(request: HttpRequest) -> HttpResponse:
    """Show the history of task runs, newest first, with filters and pages.

    The filters are `label` (the exact label of a run), `status`, `trigger`, and `page`. A
    `status` or `trigger` value that is not a valid choice is ignored. The page also shows the
    setting `OPS_RETENTION_DAYS`, which tells how long the rows are kept.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/runs.html`.
    """
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
        "OPS_RETENTION_DAYS": conf.OPS_RETENTION_DAYS,
        "triggers": RUN_TRIGGER_FILTERS,
        "section": "runs",
    }
    return TemplateResponse(request, "ops/runs.html", context)


@staff_required
def run_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show one task run with its result, its error, and its output.

    A Datastar request gets only the run panel. The page uses this to refresh itself while the
    run is active.

    Args:
        request: The HTTP request. The staff check already passed.
        pk: The primary key of the `TaskRun`, from the URL.

    Returns:
        The page `ops/run_detail.html`, or the panel `ops/_run_panel.html` for Datastar.

    Note:
        `get_object_or_404` gives a 404 response when the run does not exist.
    """
    run = get_object_or_404(TaskRun.objects.select_related("triggered_by"), pk=pk)
    template = "ops/_run_panel.html" if is_datastar(request) else "ops/run_detail.html"
    return TemplateResponse(request, template, {"run": run, "section": "runs"})


@superuser_post_required
def run_stop(request: HttpRequest, pk: int) -> HttpResponse:
    """Stop a current task run and mark it failed if it is still active.

    Celery revokes the task with `terminate=True` so a worker that has already started the job is
    interrupted. The row is marked as failed immediately so the app does not leave the task in a
    hung `pending` or `started` state.

    Args:
        request: The POST request of a superuser.
        pk: The primary key of the `TaskRun` to stop.

    Returns:
        A redirect back to the task run page.

    Raises:
        Http404: If the run does not exist.
    """
    run = get_object_or_404(TaskRun, pk=pk)
    if not run.is_active:
        messages.error(request, "This task is no longer running.")
        return redirect("ops:run", pk=pk)
    try:
        from config.celery import app  # noqa: PLC0415

        app.control.revoke(run.task_id, terminate=True, signal="SIGKILL")
    except Exception as exc:  # pragma: no cover - celery failure is operational, not logic
        messages.error(request, f"Could not stop this task: {exc}")
        return redirect("ops:run", pk=pk)
    now = timezone.now()
    if not run.error:
        run.error = "The run was stopped by an admin."
    else:
        run.error = f"{run.error}\nThe run was stopped by an admin."
    run.status = TaskRun.Status.FAILURE
    run.finished_at = now
    if run.started_at:
        run.duration_ms = max(0, int((now - run.started_at).total_seconds() * 1000))
    else:
        run.duration_ms = 0
    run.save(update_fields=["status", "finished_at", "duration_ms", "error"])
    audit.record(request.user, "stop run", run.label, f"run {run.pk}", request)
    messages.success(request, f"Stopped: {run.label}.")
    return redirect("ops:run", pk=pk)


@superuser_required
def log_view(request: HttpRequest) -> HttpResponse:
    """Show the entries of the log file, newest first, with filters.

    Only superusers can read the application log. The filters are `level` (the lowest level),
    `logger` (part of the logger name), `q` (part of the message), `limit` (the number of entries),
    and `live` (the text `true` turns on the automatic refresh). The view passes the filters to
    `logs.query`, which reads the end of the log file. A Datastar request gets only the HTML of the
    log panel.

    Args:
        request: The HTTP request.         The superuser check already passed.

    Returns:
        The page `ops/logs.html`, or the panel `ops/_log_panel.html` for Datastar.

    Security:
        `logs.query` redacts the messages before they leave the log reader.
    """
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
    return TemplateResponse(request, template, context)


@staff_required
def metric_view(request: HttpRequest) -> HttpResponse:
    """Show the numbers about the host, the queue, the database, the jobs, and the data.

    The numbers are the task statistics of the last 7 days, the daily charts, the table row
    counts, the database size, the host, Redis, the Celery workers, the LLM server, and the
    prediction accuracy. The `metrics` module collects them.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/metrics.html`.
    """
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
    return TemplateResponse(request, "ops/metrics.html", context)


@staff_required
def user_list(request: HttpRequest) -> HttpResponse:
    """Show all users with their login count, their sessions, and their access state.

    The filter `q` searches the user name and the e-mail address. Each row has the user, the
    number of active sessions, and the values of `views_access.summary` (state, subscription,
    days left, and number of removed features). Staff and superusers come first, then the users
    in order of user name.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/users.html`.
    """
    filters = read_filters(request, USER_FILTERS)
    sessions: dict[int, int] = {}
    for session in users.active_sessions():
        sessions[session.user_id] = sessions.get(session.user_id, 0) + 1
    now = timezone.now()
    rows = [
        {"user": user, "sessions": sessions.get(user.pk, 0), **views_access.summary(user, now)}
        for user in users.users_with_stats(filters["q"])
    ]
    context = {"rows": rows, "filters": filters, "section": "users"}
    return TemplateResponse(request, "ops/users.html", context)


@staff_required
def user_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show one user: details, sessions, login events, actions, runs, and access.

    The page shows the active sessions, the last 30 login events, the last 10 failed logins for
    the user name, the last 15 actions in the Django admin, the last 15 actions on the Ops pages,
    and the last 10 task runs that the user started. It also has the access panel from
    `views_access.panel`. The context key `subject` is the user that the page is about. The key
    `current_key` is the session key of the admin who looks at the page.

    Args:
        request: The HTTP request. The staff check already passed.
        pk: The primary key of the user, from the URL.

    Returns:
        The page `ops/user_detail.html`.

    Note:
        `get_object_or_404` gives a 404 response when the user does not exist.
    """
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
        "api_tokens": ApiToken.objects.filter(user=user)[:20],
        "section": "users",
        **views_access.panel(user),
    }
    return TemplateResponse(request, "ops/user_detail.html", context)


@superuser_post_required
def user_end_sessions(request: HttpRequest, pk: int) -> HttpResponse:
    """End one session of a user, or all sessions of the user.

    If the POST field `key` is set, the view ends that session. The session must belong to the
    user. If `key` is empty, the view ends all sessions of the user. The session of the admin who
    clicks is never ended. In that case the view shows an error message.

    Args:
        request: The POST request of a superuser.
        pk: The primary key of the user, from the URL.

    Returns:
        A redirect to the user page.

    Raises:
        Http404: If `key` is not the key of an active session of this user.

    Side effects:
        Deletes `Session` rows and writes the audit event `end sessions`.
    """
    user = get_object_or_404(get_user_model(), pk=pk)
    current = request.session.session_key or ""
    key = request.POST.get("key", "")
    if opaque := request.POST.get("session"):
        key = next(
            (
                session.key
                for session in users.sessions_of(user.pk)
                if constant_time_compare(
                    salted_hmac("ops-session-action", session.key, algorithm="sha256").hexdigest(),
                    opaque,
                )
            ),
            None,
        )
        if key is None:
            raise Http404
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
def user_revoke_tokens(request: HttpRequest, pk: int) -> HttpResponse:
    """Revoke one API token (with `token`) or all active API tokens of a user.

    Args:
        request: A POST request. The optional field `token` holds the id of one token.
        pk: The id of the user who owns the tokens.

    Returns:
        A redirect to the user page.

    Raises:
        Http404: If `token` is not a token of this user.
    """
    user = get_object_or_404(get_user_model(), pk=pk)
    token_id = request.POST.get("token", "")
    if token_id:
        if not token_id.isdigit():
            raise Http404
        row = get_object_or_404(ApiToken, pk=int(token_id), user=user)
        count = int(tokens.revoke(row))
        detail = row.display
    else:
        count = tokens.revoke_all(user)
        detail = f"{count} revoked"
    if count:
        audit.record(request.user, "revoke api tokens", user.get_username(), detail, request)
    messages.success(request, f"Revoked {count} API token(s) of {user.get_username()}.")
    return redirect("ops:user", pk=pk)


@superuser_post_required
def user_set_active(request: HttpRequest, pk: int) -> HttpResponse:
    """Turn a user on or off.

    The POST field `active` must be `yes` to turn the user on. Any other value turns the user
    off. A user that is off cannot log in. `users.set_user_active` also ends the sessions of that
    user. It refuses to turn off the admin's own account or the last active superuser. The view
    then shows the error message and changes nothing.

    Args:
        request: The POST request of a superuser.
        pk: The primary key of the user, from the URL.

    Returns:
        A redirect to the user page.

    Side effects:
        Saves `is_active` of the user and writes the audit event `turn on user` or
        `turn off user`.
    """
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
    """Show the login events, the failing addresses, and the locked addresses.

    The filters are `kind` (login, logout, or failed), `q` (part of the user name, or the start
    of an address), `hours` (one of the keys of `LOGIN_HOURS`, or empty for all), and `page`. The
    page also lists the addresses with the most failed logins in the last 24 hours and the
    addresses that django-axes locks now.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/logins.html`.
    """
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
        "lockouts": users.lockouts(),
        "section": "logins",
    }
    return TemplateResponse(request, "ops/logins.html", context)


@staff_required
def audit_list(request: HttpRequest) -> HttpResponse:
    """Show the audit trail of the Ops pages, newest first, in pages.

    Args:
        request: The HTTP request. The staff check already passed. The query parameter `page`
            selects the page.

    Returns:
        The page `ops/audit.html`.
    """
    filters = read_filters(request, ("page",))
    context = {
        "page": _paginate(AuditEvent.objects.select_related("actor"), filters),
        "qs": "",
        "section": "audit",
    }
    return TemplateResponse(request, "ops/audit.html", context)


@staff_required
def config_view(request: HttpRequest) -> HttpResponse:
    """Show the read-only list of the settings, with the secrets hidden.

    `configview.sections` builds the list. It shows only the text "set (hidden)" or "not set" for
    a secret.

    Args:
        request: The HTTP request. The staff check already passed.

    Returns:
        The page `ops/config.html`.
    """
    return TemplateResponse(
        request,
        "ops/config.html",
        {"sections": configview.sections(), "section": "config", "now": timezone.now()},
    )


@superuser_post_required
def lockout_unlock(request: HttpRequest) -> HttpResponse:
    """Unlock an address that django-axes locked out.

    The view removes the failed tries of the address, so that the address can try to log in
    again.

    Args:
        request: The POST request of a superuser. The field `ip_address` has the address.

    Returns:
        A redirect to the login list.

    Raises:
        Http404: If the field `ip_address` is missing or empty.

    Side effects:
        Deletes the django-axes records of the address and writes the audit event
        `unlock address`.
    """
    address = request.POST.get("ip_address", "").strip()
    if not address:
        raise Http404
    count = users.unlock(address)
    audit.record(request.user, "unlock address", address, f"{count} record(s) removed", request)
    messages.success(request, f"{address} can try to log in again.")
    return redirect("ops:logins")
