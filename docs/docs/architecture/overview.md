---
title: Architecture overview
sidebar_label: Overview
description: The services, the apps and the main design rules of Kash Engine.
---

# Architecture overview

Kash Engine is a Django project. It has one app for each part of the product. Celery workers do
slow work outside web requests. Celery beat starts the work on a schedule. PostgreSQL keeps the
data. Redis is the Celery broker and the cache of the API rate limit. Ollama runs the local
language model. Silo keeps the backup files. Caddy is the only public service.

The main user interface is a React app (see [User interface](#user-interface)). Django serves
the app and two HTTP APIs for it.

```text
                       Internet
                          |
                  +-------v-------+
                  |     caddy     |  TLS, security headers, admin IP limit
                  +---+-------+---+-----------------+
          /docs/*     |       |    everything else  |  /ws/*
              +-------v-+   +-v-------------------+ +-v--------------------+
              |  docs   |   |   web (Django)      | | realtime (Channels)  |
              | (nginx) |   |  gunicorn 3x16 thr  | | uvicorn, WebSockets  |
              +---------+   +--+---------------+--+ +----------+-----------+
                               |               |               |
                        +------v-----+   +-----v------+        |
                        | PostgreSQL |   |   Redis    |<-------+
                        +------^-----+   +-----^------+
                               |               |
              +----------------+---------------+--------------+
              |  worker (Celery)   beat (Celery)   streamer   |
              +--------+----------------------+---------------+
                       |                      |
                 +-----v-----+        news, quotes, Telegram,
                 |  Ollama   |        Upstox market feed (egress)
                 +-----------+
```

## Services

| Service | What it does | Network (production) |
| --- | --- | --- |
| `caddy` | Terminates TLS. Routes `/docs` to `docs`, `/ws/*` to `realtime` and all other paths to `web`. Adds security headers. Limits `/admin/`, `/ops/`, `/app/ops/`, and `/api/app/ops/` to `ADMIN_ALLOWED_IPS`. | `edge` and `proxy` |
| `web` | Django. The production command runs `migrate`, then `collectstatic`, then Gunicorn with 3 workers and 16 threads for each worker (`gthread`). | `proxy` and `backend` |
| `realtime` | Django Channels on Uvicorn (ASGI). It serves only the live quote WebSocket `/ws/live/quotes/`. It relays the messages of the stream worker from the Redis channel layer. | `proxy` and `backend` |
| `streamer` | `python manage.py stream_upstox`: the one Upstox market-data WebSocket (full mode). It saves the newest value of each instrument and broadcasts it about once a second. | `backend` and `egress` |
| `worker` | Runs the Celery tasks. | `backend` and `egress` |
| `beat` | Sends the scheduled tasks. The schedule is in the database (`django-celery-beat`). | `backend` and `egress` |
| `db` | PostgreSQL 17. It keeps all data. | `backend` |
| `redis` | The Celery broker, the Django cache (database 1) for the API rate limit, and the Channels layer (database 2) for live quotes. | `backend` |
| `ollama` | The local language model server. | `backend` and `egress` (model download) |
| `silo` | S3-compatible object storage for backups. It replaced MinIO. The volume name `minio_data` and the `MINIO_ROOT_*` variables stay the same. | `backend` |
| `silo-init` | Runs one time at start. It makes the private buckets and never deletes objects. | `backend` |
| `docs` | nginx with the static documentation site. It has no secret and no database. | `proxy` |

In development, a `frontend` service also runs the Vite server on `127.0.0.1:5173`. The
production image has no such service. The `Dockerfile` builds the React app in a first stage
(`frontend-build`) and copies `frontend/dist` into the image.

The `proxy` and `backend` networks have no route to the internet. Only `edge` and `egress` do.
Only Caddy publishes ports (80, 443 TCP and 443 UDP).

## Apps

| Path | What it does |
| --- | --- |
| `apps/news/` | Reads RSS feeds, scrapes article text, scores sentiment with the LLM. |
| `apps/companies/` | Companies, name matching in news, Screener.in data, saved Upstox quotes, history and fundamentals, and the company outlook. |
| `apps/markets/` | Instruments, quotes, the trading calendar, the Nifty 50 prediction and its evaluation, and the Upstox client and stream worker. |
| `apps/ipos/` | IPOs, GMP and subscription data, listing results, and the IPO score. |
| `apps/reports/` | Builds the daily report from the stored data. |
| `apps/delivery/` | Sends the report by email and on Telegram, keeps a delivery log, and keeps the sign-up invitations, the email verification and the Telegram links. |
| `apps/llm/` | The client of the local LLM server. |
| `apps/web/` | The React application shell, public landing and sign-in screens, sign-up, and legal pages. |
| `apps/api/` | The public read-only HTTP API (`/api/v1/`), the tokens, the Swagger page, the private API of the React app (`/api/app/`), and the live updates. |
| `apps/access/` | Features and subscriptions: who may use what. |
| `apps/siteconfig/` | Settings that a superuser changes on the dashboard. Encrypted secrets. |
| `apps/ops/` | The Ops pages: health, jobs, runs, logs, users, audit, schedule, settings, and backups. |
| `frontend/` | The React app (Vite, TanStack Router and Table, Mantine). It has its own tests and a generated API client. |
| `config/` | Django settings (`base`, `dev`, `prod`), URLs, Celery, beat. |
| `deploy/caddy/` | The Caddyfile for development and production. |
| `deploy/silo/` | The script that makes the buckets. |
| `docs/` | This documentation site and its generators. |

The [Python reference](../reference/generated/python/index.md) lists every module.

## User interface

The React app is the main interface. Django serves its shell, and `django-vite` reads the Vite
manifest in `frontend/dist`. The app calls the private API. It never calls the public API.

| Host | What it shows | Who can use it |
| --- | --- | --- |
| `SITE_ADDRESS` | The landing page, the React app, and the React Ops pages at their canonical URLs. | Everyone for the landing page. A signed-in user for the app. A staff user for Ops. |

## Two HTTP APIs

| API | Path | For | Contract |
| --- | --- | --- | --- |
| Public | `/api/v1/` | Your own programs. | `docs/openapi/v1.json`. It is stable inside a major version. |
| Private | `/api/app/` | The React app only. | `frontend/openapi/app.json`. It can change at any time. |

The private API accepts a browser session only. It does not accept a bearer token. A test checks
that the two contracts stay separate. The React client in
`frontend/src/shared/api/generated` is made from the private contract (`pnpm api:generate`).
See [HTTP API overview](../api/overview.md).

## Live updates

The React app refreshes its data without a page reload. The mechanism is simple:

1. A save or a delete of a model row writes a short `LiveEvent` row. The write waits for the end
   of the database transaction (`transaction.on_commit`). A rollback sends nothing.
2. The browser holds a Server-Sent Events (SSE) stream at `/api/app/events`. Staff also hold
   `/api/app/ops/events`. The stream reads new events from the database, so the web and worker
   processes share them.
3. An event says which part of the app changed (the `scope`). It never contains business data,
   task output or a secret. A task event holds only the run id, the label and the status.
4. The app refetches only the queries of that scope.

Live market prices use a second, separate path. SSE stays on the WSGI `web` service, because
Django buffers a blocking stream under ASGI.

1. The `streamer` service reads the Upstox V3 feed in full mode. It writes the newest value of
   each instrument to `LiveSnapshot`, and one `CompanyQuote` in 5 seconds at most. It writes with
   `bulk_create`, so no model signal and no SSE event is sent for a tick.
2. About once a second, it sends the changed quotes to the Redis channel layer: the group
   `live.indices` for indices, and `live.company.<id>` for each company.
3. The `realtime` service holds the browser WebSocket `/ws/live/quotes/`. It accepts a socket
   only from the same origin, for a signed-in account with Markets access. It re-checks the
   session each minute. It sends a snapshot from `LiveSnapshot` first, then relays the group
   messages.
4. The Today page and the company page show the values. A tick older than a minute is shown as
   delayed.

Each stream lasts about 20 seconds. Then the server sends `reconnect`, and the browser opens a
new stream with `Last-Event-ID`, so no event is lost. If the browser is too late, the server
asks for a full refresh. The server checks the session again at each new stream. The `ops.prune`
task deletes events that are older than one day.

Each open stream holds one Gunicorn thread and reads the database one time each second. This
is why Gunicorn uses threads. See [Troubleshooting](../operations/troubleshooting.md).

Code that writes many rows outside a task must call `apps.api.live.publish("all")` when it
finishes.

## Design rules

- **No slow work in a web request.** Collection, scraping and scoring are Celery tasks.
- **One place for each setting.** A value that an operator may change goes in the registry
  (`apps/siteconfig/registry.py`) and is read with `conf`. A value that decides how the process
  starts stays in the environment. See [Settings](./../operations/runtime-configuration.md).
- **The database holds the data that an operator edits:** feeds, instruments, the schedule and
  the settings. Migrations put the first values there.
- **Secrets stay secret.** They are not in logs, in the audit trail, in task results or in
  error messages. The Telegram bot token is encrypted in the database. See
  [Security](../operations/security.md).
- **Each part says what is missing.** A prediction or a report does not hide missing data. The
  health checks show stale data.
- **Normal users never see infrastructure errors.** Staff find the details on the Ops pages.
- **The API and the web app share one set of access rules** (`apps/access/rules.py`).
