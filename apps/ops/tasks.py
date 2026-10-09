"""Celery tasks of the ops app."""

import io
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

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
    """Run one management command from the allowed list and save what it printed."""
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
    """Delete old history and mark lost runs as failed."""
    now = timezone.now()
    keep_since = now - timedelta(days=settings.OPS_RETENTION_DAYS)
    audit_since = now - timedelta(days=max(settings.OPS_RETENTION_DAYS, AUDIT_KEEP_DAYS))

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
