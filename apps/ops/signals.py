"""Record task runs (Celery signals) and logins (Django auth signals).

A failure in this code must never break a task or a login. Each receiver logs the problem and
goes on.

The module connects its receivers when it is imported. `OpsConfig.ready` in `apps.py` imports it.
Celery signals fill the `TaskRun` table: `task_prerun`, `task_failure`, and `task_postrun`. Django
auth signals fill the `LoginEvent` table: `user_logged_in`, `user_logged_out`, and
`user_login_failed`. Internal Celery tasks (names that start with `celery.`) are not recorded.
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
    """Return `text` as a string, cut to `limit` characters.

    If the string is longer than `limit`, the function keeps the first `limit - 1` characters and
    adds the character "…". So the result is never longer than `limit`.

    Args:
        text: Any object. The function converts it with `str()`.
        limit: The largest length of the result, in characters.

    Returns:
        The string, or the cut string that ends with "…".
    """
    value = str(text)
    return value if len(value) <= limit else value[: limit - 1] + "…"


@task_prerun.connect
def on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **_extra) -> None:
    """Mark the run as started. A run that an admin made on the Jobs page already has a row.

    Celery calls this receiver before a task runs. The function finds the `TaskRun` row with the
    task ID, or makes a new row with the task name as the label. A new row has the trigger
    `auto`. The function sets the status to `started`, saves the start time and the worker host
    name, and saves the arguments if the row has none. It does nothing for internal Celery tasks.
    It logs an error and returns if a database call fails.

    Args:
        task_id: The Celery task ID. It is the key of the `TaskRun` row.
        task: The task object. With `None`, the function does nothing.
        args: The positional arguments of the task. The function saves them as text, cut to
            `MAX_ARGS_CHARS`.
        kwargs: The keyword arguments of the task. The function saves them with `args`.
        **_extra: Other signal arguments. The function ignores them.

    Side effects:
        Creates or updates one `TaskRun` row.
    """
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
    """Save the error and the traceback of a failed task.

    Celery calls this receiver when a task raises an error. It runs before `on_task_postrun`.
    The function writes the traceback (or the `repr` of the exception, if there is no traceback)
    to the `error` field. It cuts the text to `MAX_ERROR_CHARS`. It does not change the status.
    `on_task_postrun` sets the status. If no row has the task ID, nothing is saved.

    Args:
        task_id: The Celery task ID.
        exception: The exception that the task raised.
        einfo: The Celery exception info with the traceback. It can be `None`.
        **_extra: Other signal arguments. The function ignores them.

    Side effects:
        Updates the `error` field of one `TaskRun` row.
    """
    try:
        TaskRun.objects.filter(task_id=task_id).update(
            error=clip(einfo if einfo is not None else repr(exception), MAX_ERROR_CHARS)
        )
    except Exception:
        logger.exception("Could not record the failure of task %s.", task_id)


@task_postrun.connect
def on_task_postrun(task_id=None, task=None, retval=None, state=None, **_extra) -> None:
    """Mark the run as done or failed, and save the result and the time.

    Celery calls this receiver after a task ends. The status is `success` only when `state` is
    `SUCCESS`. Any other state gives `failure`. The function sets the finish time. It sets the
    duration in milliseconds when the run has a start time. It saves the return value (cut to
    `MAX_RESULT_CHARS`) for a success. For a failure with no saved error, it saves the state and
    the return value as the error. It does nothing for internal Celery tasks, or when no row has
    the task ID.

    Args:
        task_id: The Celery task ID.
        task: The task object. With `None`, the function does nothing.
        retval: The return value of the task, or the exception on a failure.
        state: The Celery state name, for example `SUCCESS` or `FAILURE`.
        **_extra: Other signal arguments. The function ignores them.

    Note:
        A state such as `RETRY` also gives the status `failure`.

    Side effects:
        Updates one `TaskRun` row.
    """
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
    """Record a login in the `LoginEvent` table.

    Django sends the signal after a user logs in. The function saves the user, the user name, the
    client address, the browser name, and the session key.

    Args:
        sender: The class that sent the signal. The function does not use it.
        request: The web request. It can be `None`. Then the address and the browser are empty.
        user: The user who logged in.
        **_extra: Other signal arguments. The function ignores them.

    Side effects:
        Writes one `LoginEvent` row. On an error it logs the error and returns.
    """
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
    """Record a logout in the `LoginEvent` table.

    Django sends the signal when a user logs out. The user can be `None` if the session had no
    user. The function does not save a session key.

    Args:
        sender: The class that sent the signal. The function does not use it.
        request: The web request. It can be `None`.
        user: The user who logged out. It can be `None`.
        **_extra: Other signal arguments. The function ignores them.

    Side effects:
        Writes one `LoginEvent` row. On an error it logs the error and returns.
    """
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
    """Record a failed login. The password is never saved.

    Django sends the signal when the credentials are wrong. The function saves the user name that
    the person typed, cut to `MAX_USERNAME_CHARS`. It saves the client address and the browser
    name. The row has no user. The lockout list and the failed-login counts use these rows.

    Args:
        sender: The class that sent the signal. The function does not use it.
        credentials: The dict of typed credentials. The function reads only the `username` key.
        request: The web request. It can be `None`.
        **_extra: Other signal arguments. The function ignores them.

    Security:
        The function never reads or saves the password from `credentials`.

    Side effects:
        Writes one `LoginEvent` row. On an error it logs the error and returns.
    """
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
