---
name: kashengine-backend-change
description: Make a Django backend change in KashEngine (models, services, Celery tasks, management commands, settings, migrations, Ops jobs). Use when adding or changing domain logic in apps/ (news, markets, ipos, companies, reports, delivery, llm, siteconfig, ops, access, web).
---

# KashEngine backend change

Source of truth: `docs/docs/development/workflow.md`. Stack: Python 3.13, Django 6, django-ninja,
Celery + django-celery-beat, Redis, PostgreSQL in prod / SQLite in dev and tests, managed with `uv`.

## 1. Put the code in the app that owns the data

| Concern | App |
| --- | --- |
| Feeds, scraping, sentiment | `apps/news` |
| Quotes, prediction, instruments, Upstox streaming | `apps/markets` |
| IPO collection and scoring | `apps/ipos` |
| Company master, news linking | `apps/companies` |
| Daily report build | `apps/reports` |
| Telegram / email delivery | `apps/delivery` |
| LLM provider checks | `apps/llm` |
| Operator-editable settings and validation | `apps/siteconfig` |
| Operator controls, jobs, schedules, backups, audit | `apps/ops` |
| Public `/api/v1` and private `/api/app` | `apps/api` |

A low-level app never imports a web view.

## 2. Keep each request thin

1. View checks access and input.
2. Form or service checks domain rules.
3. Service or model changes data.
4. Celery task does long work.
5. Template / React shows the result; it never computes a decision.

## 3. Checklist

- Find every model, service, task, view, template, setting, and test the change touches.
- Write the expected behavior (test) first.
- Validate input at the boundary. Use a DB constraint for rules that must hold under concurrency.
- Wrap each external call in a small replaceable function, with a timeout and handling for each
  provider error. Never log secrets.
- Write Google-style docstrings (see the `kashengine-docstrings` skill).
- Test valid input, invalid input, limits, and failure.

### Settings

- Operator-changeable value: add it to `apps/siteconfig/registry.py`; read it with `conf`
  (cached ~5 s; the root `conftest.py` clears the cache around tests).
- Process start-up value (DB URL, Redis URL, secret key, hosts): environment only. Add it to
  `.env.example` and `.env.prod.example`.

### Celery tasks

```python
@shared_task(name="news.fetch_feeds", soft_time_limit=600)
def fetch_feeds() -> dict: ...
```

- Always set `name` and `soft_time_limit`; make tasks safe to run again.
- User-startable: add it to the job list in `apps/ops/jobs.py`.
- Scheduled: add it to `apps/ops/defaults.py` and write a data migration for existing databases.
- Ops actions that send messages or replace data need the job confirmation text and the
  superuser check.

### Migrations

- Change the model, run `uv run python manage.py makemigrations`, and read the migration.
- Never edit a migration that is already on `main`.
- Seed-data migrations must be safe to run once on a fresh database.

### Management commands

Live in `apps/<app>/management/commands/`. Common ones: `fetch_news`, `predict_market`,
`collect_ipos`, `score_ipos`, `build_report`, `send_report`, `refresh_companies`,
`refresh_instruments`, `export_openapi`.

## 4. Verify

Run the `kashengine-quality-checks` skill. Minimum for backend-only work:

```bash
uv run ruff check . && uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest apps/<app>
```
