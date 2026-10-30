---
title: Ops pages
sidebar_label: Ops pages
description: What each Ops page shows, who may change things, and how jobs run.
---

# Ops pages

The Ops pages are at `/ops/`. Caddy lets only `ADMIN_ALLOWED_IPS` reach them. Inside Django:

| User | Access |
| --- | --- |
| Anonymous | Goes to the login page. |
| Normal user | Gets 403. |
| Staff | Can look at every page except Logs. |
| Superuser | Can also read Logs and change things. Every change is a POST request and goes in the audit trail. |

A staff user cannot change anything, also when the user sends a POST request. Hiding a link is
not the control. The view checks the role. Only superusers can read application logs or use the
Grafana (`/grafana/`), Prometheus (`/prometheus/`) and GlitchTip
(`https://sentry.<SITE_ADDRESS>`) links in Ops. GlitchTip provides Sentry-compatible error
tracking and has its own user accounts.

### React task-history preview

Staff also have a read-only preview at `/app/ops/runs/` and `/app/ops/runs/{id}/`.
The TanStack history supports server-side search, job/result/trigger filters, sorting, and
pagination with bookmarkable URLs. Detail pages show stored metadata and diagnostics as plain
text; active runs refresh every three seconds until completion or an error. Staff access is
checked on every private API request before reading any run data. `ADMIN_ALLOWED_IPS` also
covers these preview pages and `/api/app/ops/`. Job execution and all other controls still use
the original Ops pages.

The audit trail also has a read-only preview at `/app/ops/audit/`, using the same staff and
admin-IP rules. Search covers recorded admins, actions, targets, details, and addresses.
Admin/action filters, sorting, and pagination operate on all retained events, not only the
visible page, and remain in the URL. Names are shown as recorded at the time of the event.
The original `/ops/audit/` remains available. Reading either page does not write audit events.

## Pages

| Page | What it shows | What a superuser can do |
| --- | --- | --- |
| Overview | The [health checks](#health-checks), the last task runs and the last logins. | Nothing. |
| Jobs | The list of [jobs](../reference/generated/system/jobs.md), the schedule, the next run and the last run. | Start a job. |
| Runs | The history of task runs with status, time, worker, result and a safe error. | Nothing. |
| Logs | The end of the application log, with search and filters for level and logger. Secrets are hidden. | Nothing. |
| Metrics | Host, database, Redis, worker and queue numbers, row counts and the prediction accuracy. | Nothing. |
| Users | Each user with the last login, login count, failed logins, open sessions, the API tokens, and the features. | Turn a user on or off, end sessions, revoke API tokens, remove a feature. |
| Subscriptions | The trial or subscription of each user, with its history. | Start, extend or end a subscription. |
| Logins | Login and logout events, and addresses with repeated failures. | Unlock a locked address. |
| Audit | Every change that was made on the Ops pages. | Nothing. |
| Settings | The [settings](./runtime-configuration.md), by group. | Change and reset values. |
| Schedule | The beat [schedule](./scheduling.md). | Add, change, turn on or off, delete and reset entries. |
| Feeds | The news feeds and the result of the last run. | Add, stop and delete feeds. |
| Instruments | The market instruments with their weight and scale. | Change instruments. |
| Config | The effective Django settings. Secret values show as `set (hidden)`. | Nothing. |

## Health checks

The overview runs these checks. Each gives `ok`, `warn`, `fail` or `skip`, and a short text.
A check that raises an error counts as failed, so one broken part cannot hide the others. The
result is kept for 10 seconds. Each check has a time limit of 2 seconds.

| Check | Result |
| --- | --- |
| Database, migrations, Redis | Fails when a call fails or a migration is not applied. |
| Celery workers | Fails when no worker answers a ping. |
| Beat | Warns when an automatic run of a scheduled task is late. It cannot judge without a task history. |
| LLM server | Warns or fails when the server cannot be reached or has no model. |
| Telegram | Warns when the token or the chat list is not set, or when the last delivery failed. It makes **no request** to Telegram. |
| Disk | Warns at 80 percent used, fails at 92 percent. |
| Memory | Warns when less than 10 percent is available, fails under 5 percent. |
| Task failures (24 hours) | Warns for 1 failed run, fails for 5 or more. |
| News | Warns when the newest article is older than `NEWS_STALE_AFTER_HOURS` (7), fails after 24 hours. |
| Scoring backlog | Warns when more than `SENTIMENT_BATCH_SIZE` articles are older than 6 hours and still not scored. |
| Quotes | Fails when there is no quote for 5 days. Warns when the evening quotes are late. |
| Prediction, report | Warns when today's prediction is missing 30 minutes after its time, or the report 10 minutes after its time. |

## How jobs run

A job is an entry in a fixed list (`apps/ops/jobs.py`). It is a Celery task or a management
command with fixed arguments. A user cannot type a command or an argument. A command job runs
inside a worker (the task `ops.run_command`), so the web server does not wait.

When a superuser starts a job:

1. The server checks that no run of the job is waiting or running (for less than 30 minutes).
2. It saves a `TaskRun` row with the user who started it, and writes the audit trail.
3. It sends the task to the broker. The message expires after one hour if no worker takes it.
4. The worker updates the row with the status, the time and a safe result.

A job with a confirm text (for example **Build and send the daily report**) needs an explicit
confirmation, because it sends a message to other people.

`ops.prune` runs every day at 03:40. It removes task runs and login events older than
`OPS_RETENTION_DAYS` (90), audit events older than the larger of `OPS_RETENTION_DAYS` and 365
days, and expired sessions. It marks a run
that stayed `pending` for 2 hours or `started` for 3 hours as failed.

## Error messages

A normal user sees a short neutral text. A staff user can follow it to the right Ops page. A page
never shows a traceback or a secret. When you add a new failure, write both texts.
