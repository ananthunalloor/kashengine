---
title: Architecture overview
sidebar_label: Overview
description: The services, the apps and the main design rules of Kash Engine.
---

# Architecture overview

Kash Engine is a Django project. It has one app for each part of the product. Celery workers do
slow work outside web requests. Celery beat starts the work on a schedule. PostgreSQL keeps the
data. Redis is the Celery broker and the cache of the API rate limit. Ollama runs the local
language model. Caddy is the only public service.

```text
                       Internet
                          |
                  +-------v-------+
                  |     caddy     |  TLS, security headers, admin IP limit
                  +---+-------+---+
          /docs/*     |       |    everything else
              +-------v-+   +-v-------------------+
              |  docs   |   |   web (Django)      |
              | (nginx) |   |   gunicorn, 3 wkrs  |
              +---------+   +--+---------------+--+
                               |               |
                        +------v-----+   +-----v------+
                        | PostgreSQL |   |   Redis    |
                        +------^-----+   +-----^------+
                               |               |
              +----------------+---------------+--------------+
              |  worker (Celery)      beat (Celery)           |
              +--------+----------------------+---------------+
                       |                      |
                 +-----v-----+        news, quotes, Telegram
                 |  Ollama   |        (network egress)
                 +-----------+
```

## Services

| Service | What it does | Network (production) |
| --- | --- | --- |
| `caddy` | Terminates TLS. Routes `/docs` to `docs` and all other paths to `web`. Adds security headers. Limits `/admin/` and `/ops/` to `ADMIN_ALLOWED_IPS`. | `edge` and `proxy` |
| `web` | Django. The production command runs `migrate`, then `collectstatic`, then Gunicorn with 3 workers. | `proxy` and `backend` |
| `worker` | Runs the Celery tasks. | `backend` and `egress` |
| `beat` | Sends the scheduled tasks. The schedule is in the database (`django-celery-beat`). | `backend` and `egress` |
| `db` | PostgreSQL 17. It keeps all data. | `backend` |
| `redis` | The Celery broker, and the Django cache (database 1) for the API rate limit. | `backend` |
| `ollama` | The local language model server. | `backend` and `egress` (model download) |
| `docs` | nginx with the static documentation site. It has no secret and no database. | `proxy` |

The `proxy` and `backend` networks have no route to the internet. Only `edge` and `egress` do.
Only Caddy publishes ports (80, 443 TCP and 443 UDP).

## Apps

| Path | What it does |
| --- | --- |
| `apps/news/` | Reads RSS feeds, scrapes article text, scores sentiment with the LLM. |
| `apps/companies/` | Companies, name matching in news, and Screener.in data. |
| `apps/markets/` | Instruments, quotes, the Nifty 50 prediction, and its evaluation. |
| `apps/ipos/` | IPOs, GMP and subscription data, listing results, and the IPO score. |
| `apps/reports/` | Builds the daily report from the stored data. |
| `apps/delivery/` | Sends the report on Telegram and keeps a delivery log. |
| `apps/llm/` | The client of the local LLM server. |
| `apps/web/` | The web pages (Django templates, Datastar, Tailwind). |
| `apps/api/` | The read-only HTTP API, the tokens, and the Swagger page. |
| `apps/access/` | Features and subscriptions: who may use what. |
| `apps/siteconfig/` | Settings that a superuser changes on the dashboard. Encrypted secrets. |
| `apps/ops/` | The Ops pages: health, jobs, runs, logs, users, audit, schedule, settings. |
| `config/` | Django settings (`base`, `dev`, `prod`), URLs, Celery, beat. |
| `deploy/caddy/` | The Caddyfile for development and production. |
| `docs/` | This documentation site and its generators. |

The [Python reference](../reference/generated/python/index.md) lists every module.

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
