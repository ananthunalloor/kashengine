---
title: Architecture overview
---

# Architecture overview

Kash Engine is a Django application with separate apps for data collection, analysis, reporting, and operations. Celery workers run work outside web requests. Celery Beat schedules recurring work. PostgreSQL stores application data. Redis provides the Celery broker. Ollama serves the configured local language model. Caddy is the only public entry point in the documented deployment.

## Runtime services

| Service | Responsibility | Network expectation |
| --- | --- | --- |
| `caddy` | Terminates TLS, adds edge security headers, routes application and documentation requests, and logs access. | Public edge; can reach `web` and `docs`. |
| `web` | Runs Django and serves HTML responses. The production command applies migrations and collects static assets before Gunicorn starts. | Private proxy and backend networks. |
| `worker` | Executes queued Celery tasks. | Backend plus restricted egress for external providers. |
| `beat` | Publishes scheduled Celery tasks. The schedule is stored in the database. | Backend plus restricted egress. |
| `db` | Stores application records, operational history, settings, schedules, sources, and instruments. | Backend only. |
| `redis` | Celery broker and runtime coordination. | Backend only. |
| `ollama` | Hosts the local model used by analysis workflows. | Backend and controlled egress for model downloads. |
| `docs` | Serves the static Docusaurus build using Nginx. It does not need application credentials or a database connection. | Private proxy network in production. |

The production Compose overlay defines the `edge`, `proxy`, `backend`, and `egress` networks. The `proxy` and `backend` networks are internal. The documentation container joins the proxy network so Caddy can reach it without publishing a port.

## Code areas

| Path | Purpose |
| --- | --- |
| `apps/news/` | News sources, retrieval, article data, and related workflow. |
| `apps/companies/` | Company data and scheduled refreshes. |
| `apps/markets/` | Market instruments, quotes, cues, predictions, and evaluation. |
| `apps/ipos/` | IPO records and scoring. |
| `apps/reports/` | Daily report composition and report history. |
| `apps/delivery/` | Outbound Telegram delivery. |
| `apps/web/` | User-facing Django views and templates. |
| `apps/ops/` | Health, jobs, task history, logs, metrics, users, audit, settings, feeds, instruments, and scheduling pages. |
| `apps/siteconfig/` | Typed registry and database-backed runtime settings. |
| `config/settings/` | Shared, development, and production Django settings. |
| `config/` | Django and Celery configuration. |
| `deploy/caddy/` | Caddy configuration shared by the development and production stacks. |
| `frontend/` | Tailwind build input and frontend build tooling. |
| `docs/` | Docusaurus content, generator, styling, and self-hosting image. |

Use the current repository tree as the final authority for module names. The generated API reference is produced from Python under `apps/`, `config/`, and `manage.py`, excluding tests and migrations.

## Main design constraints

- Web requests must not perform slow scheduled collection or analysis work synchronously. Use Celery tasks for long-running jobs.
- Configuration that operators are allowed to change at runtime belongs in the siteconfig registry and Ops UI. Deployment-only values remain environment configuration.
- Secrets must not appear in logs, audit values, exception messages, generated reports, or API documentation.
- Only Caddy publishes ports in production.
- User-visible errors must not disclose infrastructure details to ordinary users. Give staff a safe path to the Ops diagnostics.
- Database migrations own initial data seeding where the project defines a default source, instrument, or schedule.
