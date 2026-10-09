"""Record task runs (Celery signals) and logins (Django auth signals).

A failure in this code must never break a task or a login. Each receiver logs the problem and
goes on.
"""

import logging
from datetime import timedelta

from celery.signals import task_failure, task_postrun, task_prerun
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone

from .models import LoginEvent, TaskRun
from .requestinfo import client_ip, user_agent

logger = logging.getLogger(__name__)

MAX_RESULT_CHARS = 4000
MAX_ERROR_CHARS = 8000
MAX_ARGS_CHARS = 500
MAX_USERNAME_CHARS = 150
INTERNAL_TASK_PREFIX = "celery."


def clip(text: object, limit: int) -> str:
    """Return the text of `text`, cut to `limit` characters."""
    value = str(text)
    return value if len(value) <= limit else value[: limit - 1] + "…"


@task_prerun.connect
def on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **_extra) -> None:
    """Mark the run as started. A run that an admin made on the Jobs page already has a row."""
    if task is None or task.name.startswith(INTERNAL_TASK_PREFIX):
        return
    try:
        run, _created = TaskRun.objects.get_or_create(
            task_id=task_id,
            defaults={"task_name": task.name, "label": task.name},
        )
        run.status = TaskRun.Status.STARTED
        run.started_at = timezone.now()
        run.worker = clip(getattr(task.request, "hostname", "") or "", 200)
        if not run.args:
            run.args = clip(f"{args!r} {kwargs!r}" if args or kwargs else "", MAX_ARGS_CHARS)
        run.save()
    except Exception:
        logger.exception("Could not record the start of task %s.", task_id)


@task_failure.connect
def on_task_failure(task_id=None, exception=None, einfo=None, **_extra) -> None:
    """Save the error and the traceback."""
    try:
        TaskRun.objects.filter(task_id=task_id).update(
            error=clip(einfo if einfo is not None else repr(exception), MAX_ERROR_CHARS)
        )
    except Exception:
        logger.exception("Could not record the failure of task %s.", task_id)


@task_postrun.connect
def on_task_postrun(task_id=None, task=None, retval=None, state=None, **_extra) -> None:
    """Mark the run as done or failed, and save the result and the time."""
    if task is None or task.name.startswith(INTERNAL_TASK_PREFIX):
        return
    try:
        run = TaskRun.objects.filter(task_id=task_id).first()
        if run is None:
            return
        now = timezone.now()
        ok = state == "SUCCESS"
        run.status = TaskRun.Status.SUCCESS if ok else TaskRun.Status.FAILURE
        run.finished_at = now
        if run.started_at:
            run.duration_ms = max(0, int((now - run.started_at) / timedelta(milliseconds=1)))
        if ok and retval is not None:
            run.result = clip(retval, MAX_RESULT_CHARS)
        if not ok and not run.error:
            run.error = clip(f"{state}: {retval!r}", MAX_ERROR_CHARS)
        run.save()
    except Exception:
        logger.exception("Could not record the end of task %s.", task_id)


@user_logged_in.connect
def on_login(sender, request=None, user=None, **_extra) -> None:
    """Record a login."""
    try:
        LoginEvent.objects.create(
            kind=LoginEvent.Kind.LOGIN,
            user=user,
            username=user.get_username() if user else "",
            ip_address=client_ip(request),
            user_agent=user_agent(request),
            session_key=getattr(getattr(request, "session", None), "session_key", "") or "",
        )
    except Exception:
        logger.exception("Could not record a login.")


@user_logged_out.connect
def on_logout(sender, request=None, user=None, **_extra) -> None:
    """Record a logout."""
    try:
        LoginEvent.objects.create(
            kind=LoginEvent.Kind.LOGOUT,
            user=user,
            username=user.get_username() if user else "",
            ip_address=client_ip(request),
            user_agent=user_agent(request),
        )
    except Exception:
        logger.exception("Could not record a logout.")


@user_login_failed.connect
def on_login_failed(sender, credentials=None, request=None, **_extra) -> None:
    """Record a failed login. The password is never saved."""
    try:
        typed = (credentials or {}).get("username", "")
        LoginEvent.objects.create(
            kind=LoginEvent.Kind.FAILED,
            username=clip(typed, MAX_USERNAME_CHARS),
            ip_address=client_ip(request),
            user_agent=user_agent(request),
        )
    except Exception:
        logger.exception("Could not record a failed login.")
