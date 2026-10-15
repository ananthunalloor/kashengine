"""Celery tasks of the ops app.

The module has two tasks. `ops.run_command` runs a management command from the allowed list in
`jobs.py`. `ops.prune` cleans old history. The beat schedule runs `ops.prune` each day (see
`defaults.py`). The Jobs page starts both tasks through `jobs.start_job`. The module reads
`conf.OPS_RETENTION_DAYS`. Its history comes from the `TaskRun` rows that `signals.py` writes.
"""

import io
import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from apps.siteconfig import conf

from .jobs import COMMAND_ALLOWLIST
from .models import AuditEvent, LoginEvent, TaskRun
from .signals import clip

logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 20000
AUDIT_KEEP_DAYS = 365
PENDING_LOST_AFTER = timedelta(hours=2)  # A job that no worker took.
STARTED_LOST_AFTER = timedelta(hours=3)  # The longest soft time limit is one hour.


@shared_task(name="ops.run_command", bind=True, soft_time_limit=1800)
def run_command(self, command: str, args: list[str] | None = None) -> dict:
    """Run one management command from the allowed list and save what it printed.

    The Jobs page starts this task for each command job (see `jobs.start_job`). The pair of
    `command` and `args` must be in `COMMAND_ALLOWLIST`. The function runs the command with
    `call_command` and collects stdout and stderr. It writes the text to the `output` field of the
    `TaskRun` row that has the task ID of this run. It writes the text also when the command fails.
    The text has the stderr part after the line `[stderr]`. The function cuts it to
    `MAX_OUTPUT_CHARS`. The soft time limit is 1800 seconds.

    Args:
        self: The bound Celery task. The function reads `self.request.id`.
        command: The name of the management command.
        args: The fixed arguments of the command. The default is no arguments. The list must match
            an entry of `COMMAND_ALLOWLIST` exactly.

    Returns:
        A dict with `command` (the name) and `lines` (the number of lines on stdout).

    Raises:
        ValueError: If the command and the arguments are not in the allowed list.

    Side effects:
        Runs the command, with all its effects. Updates the `output` field of one `TaskRun` row.

    Security:
        Only fixed jobs can run. The allowed list stops a caller from running any other command.
        The ValueError happens before the command starts, so no output is saved for it.
    """
    arguments = tuple(args or ())
    if (command, arguments) not in COMMAND_ALLOWLIST:
        msg = f"The command is not allowed: {command} {' '.join(arguments)}"
        raise ValueError(msg)

    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        call_command(command, *arguments, stdout=stdout, stderr=stderr, no_color=True)
    finally:
        text = stdout.getvalue() + (f"\n[stderr]\n{stderr.getvalue()}" if stderr.getvalue() else "")
        TaskRun.objects.filter(task_id=self.request.id).update(output=clip(text, MAX_OUTPUT_CHARS))
    return {"command": command, "lines": len(stdout.getvalue().splitlines())}


@shared_task(name="ops.prune", soft_time_limit=300)
def prune() -> dict:
    """Delete old history and mark lost runs as failed.

    The schedule runs this task each day (`prune-ops-history`). The Jobs page can also start it.
    The function does these steps:

    1. It marks a `pending` run as failed when it is older than `PENDING_LOST_AFTER` (2 hours).
       No worker took the job.
    2. It marks a `started` run as failed when it started more than `STARTED_LOST_AFTER`
       (3 hours) ago. The worker probably stopped.
    3. It deletes task runs and login events older than `OPS_RETENTION_DAYS`.
    4. It deletes audit events older than the larger of `OPS_RETENTION_DAYS` and
       `AUDIT_KEEP_DAYS` (365 days).
    5. It deletes sessions that have expired.

    Returns:
        A dict with the number of rows for each step: `lost_pending`, `lost_started`,
        `task_runs`, `login_events`, `audit_events`, and `sessions`. The delete counts are the
        first value that Django returns, so they can include rows that a cascade deletes.

    Side effects:
        Updates and deletes rows in the `TaskRun`, `LoginEvent`, `AuditEvent`, and `Session`
        tables. Writes one log line.
    """
    now = timezone.now()
    keep_since = now - timedelta(days=conf.OPS_RETENTION_DAYS)
    audit_since = now - timedelta(days=max(conf.OPS_RETENTION_DAYS, AUDIT_KEEP_DAYS))

    lost_pending = TaskRun.objects.filter(
        status=TaskRun.Status.PENDING, created_at__lt=now - PENDING_LOST_AFTER
    ).update(
        status=TaskRun.Status.FAILURE,
        finished_at=now,
        error="The job never started. Is a worker running?",
    )
    lost_started = TaskRun.objects.filter(
        status=TaskRun.Status.STARTED, started_at__lt=now - STARTED_LOST_AFTER
    ).update(
        status=TaskRun.Status.FAILURE,
        finished_at=now,
        error="The run was lost. The worker probably stopped.",
    )
    result = {
        "lost_pending": lost_pending,
        "lost_started": lost_started,
        "task_runs": TaskRun.objects.filter(created_at__lt=keep_since).delete()[0],
        "login_events": LoginEvent.objects.filter(created_at__lt=keep_since).delete()[0],
        "audit_events": AuditEvent.objects.filter(created_at__lt=audit_since).delete()[0],
        "sessions": Session.objects.filter(expire_date__lt=now).delete()[0],
    }
    logger.info("Ops history pruned: %s", result)
    return result
