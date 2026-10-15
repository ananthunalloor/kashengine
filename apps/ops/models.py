"""Models for the admin tools: task runs, login events, and the audit trail.

The Ops pages read these three tables. The Celery and login signal receivers in
`apps/ops/signals.py` write `TaskRun` and `LoginEvent`. The function `audit.record` and the Ops
views write `AuditEvent`. The `ops.prune` task in `apps/ops/tasks.py` deletes old rows. It keeps
the task runs and the login events of the last `OPS_RETENTION_DAYS` days. It keeps the audit
trail for at least 365 days.
"""

from typing import ClassVar

from django.conf import settings
from django.db import models


class TaskRun(models.Model):
    """One run of a Celery task or of a management command.

    A run starts as `pending`. The `task_prerun` signal makes it `started`. The `task_postrun`
    signal makes it `success` or `failure`. An admin who starts a job on the Jobs page creates
    the row first (see `jobs.start_job`), and the signal receivers then reuse the row with the
    same `task_id`. The `ops.prune` task marks a run that never started, or never ended, as
    `failure`. Time stamps are timezone-aware (UTC in the database).
    """

    class Status(models.TextChoices):
        """The state of a task run: pending, started, success, or failure."""

        PENDING = "pending", "Waiting"
        STARTED = "started", "Running"
        SUCCESS = "success", "Done"
        FAILURE = "failure", "Failed"

    class Trigger(models.TextChoices):
        """What started a task run: the schedule or another task (auto), or an admin (manual)."""

        AUTO = "auto", "Automatic"  # The schedule, or another task, started it.
        MANUAL = "manual", "Manual"  # An admin started it on the Jobs page.

    task_id = models.CharField(max_length=64, unique=True)
    task_name = models.CharField(max_length=200)
    label = models.CharField(
        max_length=200, help_text="The name that the pages show. For a command: command: <name>."
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    trigger = models.CharField(max_length=10, choices=Trigger.choices, default=Trigger.AUTO)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    worker = models.CharField(max_length=200, blank=True)
    args = models.CharField(max_length=500, blank=True)
    result = models.TextField(blank=True, help_text="What the task returned. It can be cut.")
    error = models.TextField(blank=True, help_text="The error and the traceback. It can be cut.")
    output = models.TextField(blank=True, help_text="The text that a command printed.")

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-id"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["label", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        """Return the label and the status, for example `news.fetch_feeds (success)`."""
        return f"{self.label} ({self.status})"

    @property
    def is_active(self) -> bool:
        """True while the run waits or runs."""
        return self.status in {self.Status.PENDING, self.Status.STARTED}


class LoginEvent(models.Model):
    """A login, a logout, or a failed login.

    The signal receivers in `apps/ops/signals.py` create one row for each event. A failed login
    has no `user`. It keeps the typed `username` only, and never the password. The `user`
    field is set to null if the user is deleted. The `ops.prune` task deletes old rows.
    """

    class Kind(models.TextChoices):
        """The type of a login event: login, logout, or failed."""

        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        FAILED = "failed", "Failed login"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="login_events",
    )
    username = models.CharField(max_length=150, blank=True, help_text="The name that was typed.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-id"]
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["kind", "-created_at"])]

    def __str__(self):
        """Return the kind, the user name, and the time of the event."""
        return f"{self.kind} {self.username} {self.created_at:%Y-%m-%d %H:%M}"


class AuditEvent(models.Model):
    """An action of an admin on the Ops pages.

    `audit.record` creates one row each time a superuser changes something, for example starts a
    job, ends a session, or saves a setting. The row keeps `actor_name`, so the name stays after
    the user is deleted. Rows are never changed after they are written.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    actor_name = models.CharField(max_length=150, help_text="Kept when the user is deleted.")
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=200, blank=True)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-id"]

    def __str__(self):
        """Return the actor, the action, and the target."""
        return f"{self.actor_name}: {self.action} {self.target}"
