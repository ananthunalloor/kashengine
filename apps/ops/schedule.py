"""Read and change the schedule of the Celery beat tasks. It is in the database.

The tables are from django-celery-beat. The beat process (DatabaseScheduler) reads them, and it
sees a change within a few seconds. Only crontab entries are used here.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from celery.schedules import crontab
from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from . import jobs
from .defaults import DEFAULT_SCHEDULE

OVERDUE_GRACE = timedelta(minutes=10)  # Beat can be late by some seconds. This is a safe margin.
SUNDAY_FIRST_OFFSET = 1  # A crontab week starts on Sunday (0). Python's weekday() starts on Monday.
DAYS_IN_WEEK = 7


@dataclass(frozen=True)
class ScheduleEntry:
    """One line of the beat schedule."""

    pk: int
    name: str
    task: str
    enabled: bool
    minute: str
    hour: str
    day_of_week: str
    day_of_month: str
    month_of_year: str
    schedule: crontab
    last_run_at: datetime | None

    @property
    def cron_text(self) -> str:
        """The schedule as a cron line: minute hour day-of-month month day-of-week (IST)."""
        return " ".join(
            (self.minute, self.hour, self.day_of_month, self.month_of_year, self.day_of_week)
        )


def _celery_crontab(cron: CrontabSchedule) -> crontab:
    """A plain Celery crontab in the time zone of the entry.

    We do not use `cron.schedule` from django-celery-beat. Its clock uses utcnow(), which is
    deprecated. The beat process reads the same fields with its own scheduler.
    """
    zone = ZoneInfo(str(cron.timezone))
    return crontab(
        minute=cron.minute,
        hour=cron.hour,
        day_of_week=cron.day_of_week,
        day_of_month=cron.day_of_month,
        month_of_year=cron.month_of_year,
        nowfun=lambda: datetime.now(zone),
    )


def _entry(row: PeriodicTask) -> ScheduleEntry:
    cron = row.crontab
    return ScheduleEntry(
        pk=row.pk,
        name=row.name,
        task=row.task,
        enabled=row.enabled,
        minute=cron.minute,
        hour=cron.hour,
        day_of_week=cron.day_of_week,
        day_of_month=cron.day_of_month,
        month_of_year=cron.month_of_year,
        schedule=_celery_crontab(cron),
        last_run_at=row.last_run_at,
    )


def entries(*, enabled_only: bool = True) -> list[ScheduleEntry]:
    """The crontab entries of the schedule, sorted by name."""
    rows = PeriodicTask.objects.filter(crontab__isnull=False).select_related("crontab")
    if enabled_only:
        rows = rows.filter(enabled=True)
    return [_entry(row) for row in rows.order_by("name") if not row.task.startswith("celery.")]


def entries_for(task_name: str, *, enabled_only: bool = True) -> list[ScheduleEntry]:
    """The schedule entries of one task."""
    return [entry for entry in entries(enabled_only=enabled_only) if entry.task == task_name]


def next_after(cron: crontab, after: datetime) -> datetime:
    """The first time after `after` when the schedule is due.

    Celery's `remaining_estimate` gives "next time minus the clock of the schedule". It is not
    "next time minus `after`". So we compute the next time directly.
    """
    # With UTC on, Celery does not convert `after`. The cron fields are in the zone of the
    # schedule (IST), so convert `after` to that zone first.
    zone = cron.nowfun().tzinfo if cron.nowfun else ZoneInfo(settings.TIME_ZONE)
    start, delta, _now = cron.remaining_delta(after.astimezone(zone))
    return start + delta


def next_run(task_name: str, now: datetime) -> datetime | None:
    """When the task is due next, or None if it is not scheduled."""
    times = [next_after(entry.schedule, now) for entry in entries_for(task_name)]
    return min(times) if times else None


def overdue_by(task_name: str, last_run_at: datetime, now: datetime) -> timedelta | None:
    """How late the task is, if it should have run after `last_run_at`. None if it is on time."""
    entries_of_task = entries_for(task_name)
    if not entries_of_task:
        return None
    due_at = min(next_after(entry.schedule, last_run_at) for entry in entries_of_task)
    late = now - due_at
    return late if late > OVERDUE_GRACE else None


def times_on(task_name: str, day: date) -> list[tuple[int, int]]:
    """The (hour, minute) times when the task is scheduled on a day, sorted."""
    weekday = (day.weekday() + SUNDAY_FIRST_OFFSET) % DAYS_IN_WEEK  # 0 = Sunday, like cron.
    times: list[tuple[int, int]] = []
    for entry in entries_for(task_name):
        cron = entry.schedule
        if (
            weekday in cron.day_of_week
            and day.day in cron.day_of_month
            and day.month in cron.month_of_year
        ):
            times.extend((hour, minute) for hour in cron.hour for minute in cron.minute)
    return sorted(set(times))


def schedulable_tasks() -> dict[str, str]:
    """The tasks that an admin can schedule: {task name: job label}."""
    return {job.target: job.label for job in jobs.JOBS if job.kind == jobs.TASK}


def parse_cron(minute: str, hour: str, day_of_week: str, day_of_month: str, month: str) -> crontab:
    """Check the five cron fields. Raise ValueError with a short reason if they are bad."""
    try:
        zone = ZoneInfo(settings.TIME_ZONE)
        return crontab(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month,
            nowfun=lambda: datetime.now(zone),
        )
    except Exception as exc:  # Celery raises ParseException, ValueError, and others.
        msg = f"The schedule is not valid: {exc}"
        raise ValueError(msg) from exc


def preview(cron: crontab, now: datetime, count: int = 3) -> list[datetime]:
    """The next `count` times that a schedule is due."""
    times = []
    cursor = now
    for _ in range(count):
        cursor = next_after(cron, cursor)
        times.append(cursor)
    return times


def _crontab_row(minute: str, hour: str, day_of_week: str, day_of_month: str, month: str):
    row, _created = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year=month,
        timezone=settings.TIME_ZONE,
    )
    return row


def save_entry(  # noqa: PLR0913
    pk: int | None,
    *,
    name: str,
    task: str,
    minute: str,
    hour: str,
    day_of_week: str,
    day_of_month: str,
    month: str,
    enabled: bool,
) -> PeriodicTask:
    """Add or change an entry. Raise ValueError if the schedule or the task is not valid."""
    if task not in schedulable_tasks():
        msg = "This task cannot be scheduled."
        raise ValueError(msg)
    parse_cron(minute, hour, day_of_week, day_of_month, month)
    name = name.strip()
    if not name:
        msg = "Enter a name."
        raise ValueError(msg)
    clash = PeriodicTask.objects.filter(name=name).exclude(pk=pk)
    if clash.exists():
        msg = "Another entry has this name."
        raise ValueError(msg)
    cron = _crontab_row(minute, hour, day_of_week, day_of_month, month)
    if pk is None:
        return PeriodicTask.objects.create(name=name, task=task, crontab=cron, enabled=enabled)
    row = PeriodicTask.objects.get(pk=pk)
    row.name, row.task, row.crontab, row.enabled = name, task, cron, enabled
    row.save()
    return row


def reset_to_default() -> int:
    """Delete all entries of the tasks in the default list, and add the default entries again."""
    names = {task for _n, task, *_rest in DEFAULT_SCHEDULE}
    PeriodicTask.objects.filter(task__in=names).delete()
    for name, task, minute, hour, day_of_week in DEFAULT_SCHEDULE:
        cron = _crontab_row(minute, hour, day_of_week, "*", "*")
        PeriodicTask.objects.create(name=name, task=task, crontab=cron, enabled=True)
    return len(DEFAULT_SCHEDULE)
