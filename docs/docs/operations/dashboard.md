---
title: Ops dashboard
---

# Ops dashboard

The Ops interface is under `/ops/`. Staff users can inspect operational data. Mutating actions are restricted to superusers. Anonymous users are redirected to login; ordinary authenticated users do not gain Ops privileges merely because they can sign in.

## Pages

| Page | Purpose |
| --- | --- |
| Overview | Health of PostgreSQL, Redis, Celery workers and Beat, Ollama, Telegram, host resources, migrations, data freshness, scoring backlog, quotes, prediction, reports, and task failures. |
| Jobs | Registered scheduled and manual jobs, schedule, next run, last run, and recent counts. Superusers can start eligible jobs. |
| Runs | Persistent history of automated and manual runs, including status, timing, worker, result, and safe error output. |
| Logs | Recent application log records with filters. Tokens and passwords must be redacted. |
| Metrics | Recent database, table, host, Redis, worker, queue, and prediction accuracy measurements. |
| Users | Accounts, last login, login count, failed login events, and active sessions. Superusers can change active status or end sessions. |
| Logins | Login/logout/failed-login events and suspicious repeated failures. |
| Audit | Changes made through administrative pages. Secret values must be represented as “changed,” never as old/new plaintext. |
| Settings | Runtime settings grouped by concern. Only superusers can change values. |
| Schedule | Database-backed Celery Beat schedule. Add, edit, disable, delete, or reset supported entries. |
| Feeds | Enabled news sources and their latest fetch outcomes. |
| Instruments | Market target, index, and cue definitions and associated weight/scale values. |
| Config | Effective setting values, with secret values hidden. |
| Logins / unlock | Review login lockouts and unlock a client address when appropriate. |

## Job execution model

Jobs are a fixed registry of Celery tasks or management commands. An operator must not be able to type an arbitrary shell command. The server creates a run record for a manual action; a worker updates its status. A job that is waiting or running must not start again. Jobs that can send a message or replace data should ask for explicit confirmation.

The `ops.prune` task removes operational records according to the configured retention policy, removes expired sessions, and marks abandoned runs as failed. Confirm the actual task schedule and policy in Ops > Schedule and the source before changing retention behavior.

## Safe diagnostics

Normal users should receive neutral error messages. Staff can be directed to the relevant Ops page, but the page must still avoid secret disclosure. Do not render raw tracebacks into user-facing templates. When adding a new failure state, define the staff diagnostic and ordinary-user wording together.

## Authorization tests

For every read and mutation endpoint, test anonymous, ordinary user, staff user, and superuser access. Do not rely only on hiding a navigation link. Authorization must be enforced by the view or its shared access-control boundary.
