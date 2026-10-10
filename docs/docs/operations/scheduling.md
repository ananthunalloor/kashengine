---
title: Scheduling and task runs
---

# Scheduling and task runs

Kash Engine uses `django-celery-beat` with `django_celery_beat.schedulers:DatabaseScheduler`. The production and development Beat commands are `celery -A config beat -l info`; do not configure a second file-based schedule.

## Editing the schedule

Open Ops > Schedule. Superusers can add or edit a schedule entry, turn it on or off, delete supported entries, or reset the schedule to defaults. The default schedule is seeded by a migration and defined in `apps/ops/defaults.py`. At the point recorded in the Phase 13 project summary, the default set had 13 entries and used IST.

Use the scheduling helpers in `apps/ops/schedule.py` instead of duplicating cron calculations. They cover entry enumeration, task eligibility, cron parsing, preview, next-run calculation, overdue calculations, and save/reset operations.

## Schedule correctness

- Use the schedule's configured time zone for cron parsing and next-run calculation.
- Convert the current time to the schedule zone before calculating the next run.
- Do not assume Celery automatically converts a cron time into the application's intended market time zone.
- A task not scheduled for the current day should not be reported as overdue for that day.
- Health checks apply grace periods to prediction and report tasks; check the current helper and registry before changing them.
- Treat disabled tasks as intentionally not due.

## Adding a job

1. Implement a named Celery task or fixed management command.
2. Register it in the Ops job registry with a stable key, label, task/command target, and confirmation requirement where needed.
3. Add a default schedule entry only if the task should run automatically.
4. Document task arguments, side effects, idempotency, timeout/retry policy, and what success means.
5. Add task tests and schedule/health tests.
6. Verify that manual runs cannot bypass authorization or launch duplicate active runs.

Never accept arbitrary command strings from an HTTP request. A job registry is an allowlist, not a shell interface.
