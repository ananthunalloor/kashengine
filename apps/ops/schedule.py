"""Read the Celery beat schedule (CELERY_BEAT_SCHEDULE) for the Ops pages."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from celery.schedules import crontab
from django.conf import settings

CRON_FIELDS = ("minute", "hour", "day_of_month", "month_of_year", "day_of_week")
OVERDUE_GRACE = timedelta(minutes=10)  # Beat can be late by some seconds. This is a safe margin.


@dataclass(frozen=True)
class ScheduleEntry:
    """One line of the beat schedule."""

    name: str
    task: str
    schedule: crontab

    @property
    def cron_text(self) -> str:
        """The schedule as a cron line: minute hour day-of-month month day-of-week (IST)."""
        # Celery keeps the text that was given in attributes with this prefix. It has no getter.
        return " ".join(str(getattr(self.schedule, f"_orig_{name}")) for name in CRON_FIELDS)


def entries() -> list[ScheduleEntry]:
    """All crontab entries of the beat schedule."""
    found = []
    for name, item in settings.CELERY_BEAT_SCHEDULE.items():
        if isinstance(item.get("schedule"), crontab):
            found.append(ScheduleEntry(name=name, task=item["task"], schedule=item["schedule"]))
    return found


def entries_for(task_name: str) -> list[ScheduleEntry]:
    """The schedule entries of one task."""
    return [entry for entry in entries() if entry.task == task_name]


def next_run(task_name: str, now: datetime) -> datetime | None:
    """When the task is due next, or None if it is not scheduled."""
    waits = [entry.schedule.remaining_estimate(now) for entry in entries_for(task_name)]
    return now + min(waits) if waits else None


def overdue_by(task_name: str, last_run_at: datetime, now: datetime) -> timedelta | None:
    """How late the task is, if it should have run after `last_run_at`. None if it is on time."""
    entries_of_task = entries_for(task_name)
    if not entries_of_task:
        return None
    soonest = min(entry.schedule.remaining_estimate(last_run_at) for entry in entries_of_task)
    due_at = last_run_at + soonest
    late = now - due_at
    return late if late > OVERDUE_GRACE else None
