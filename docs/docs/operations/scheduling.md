---
title: Scheduling
sidebar_label: Scheduling
description: How the beat schedule is stored, how to change it, and how to add a job.
---

# Scheduling

Kash Engine uses `django-celery-beat` with the `DatabaseScheduler`. The beat command is
`celery -A config beat -l info`. There is **no** second schedule in a file or in settings.

The default entries are in [Default schedule](../reference/generated/system/schedule.md). The
first migration saves them. All times are IST.

## Change the schedule

On **Ops > Schedule** a superuser can add, change, turn on or off, and delete an entry, and can
**reset** the schedule to the defaults (`apps/ops/defaults.py`). Beat sees a change in a few
seconds. Only cron entries are used. Each entry has the five cron fields: minute, hour, day of
month, month and day of week.

The page shows the next three run times of an entry before you save it.

## Rules

- **The clock is IST.** The code converts the current time to the zone of the schedule before it
  computes a next run. Celery does not do this by itself. Use the helpers in
  `apps/ops/schedule.py` (`next_after`, `next_run`, `parse_cron`, `preview`), not your own
  calculation.
- **Disabled means not due.** The health check does not report a disabled task as late.
- **A task that does not run today is not late today.** `times_on` tells which times a task has on
  a day.
- **Late means more than 10 minutes** after the time (`OVERDUE_GRACE`). The health check gives the
  prediction 30 minutes and the report 10 minutes.

## Add a job

1. Write a Celery task with `@shared_task(name="app.name", soft_time_limit=...)`.
2. Make it safe to run again. See [Reliability](../architecture/reliability.md).
3. If a superuser may start it, add a `Job` to `apps/ops/jobs.py` with a stable key, a label, the
   target and a confirm text if it sends a message or replaces data.
4. If it runs on a schedule, add an entry to `DEFAULT_SCHEDULE` in `apps/ops/defaults.py`, and write
   a data migration that adds it to existing databases.
5. Write the docstring of the task: the arguments, the result, the side effects and what success
   is.
6. Write tests for the task, the schedule and the health check.

The job list is an allowlist. Never accept a command text from an HTTP request.
