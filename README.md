# Kash Engine

A bot that sends a daily report on Indian financial news. It reads news from the previous day, scores the sentiment, and predicts how the market will move on the next day. It also lists IPOs to watch.

> Not financial advice. Predictions can be wrong.

## Status

Early development. Phase 1 (project setup) is done. The features below are planned.

- Collect news from free RSS feeds and web pages
- Save company data from Screener.in and update it on a schedule
- Score news sentiment with a local open model (Ollama)
- Predict the next-day market direction
- Score and list upcoming IPOs
- Send the daily report with Telegram (email later)
- Show all data in a web UI (Django, Datastar, Tailwind)

## Stack

- Python 3.13, Django, Celery, Redis
- PostgreSQL
- Ollama (local LLM)
- Docker and Docker Compose
- uv (packages) and ruff (lint and format)

## Project layout

```text
apps/       Django apps: news, companies, ipos, reports, delivery
config/     Django project, settings (base, dev, prod), Celery
```

## Run in development

You need Docker and Docker Compose.

1. Make the env file:

   ```bash
   cp .env.example .env.dev
   ```

2. Start all services:

   ```bash
   docker compose up --build
   ```

3. Open <http://localhost:8000/admin/>.
4. Make an admin user:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

5. Download the dev model:

   ```bash
   docker compose exec ollama ollama pull llama3.2:3b
   ```

Dev has hot-reload. The web server, the Celery worker, and Celery beat restart when you change a `.py` file. Rebuild with `docker compose up --build` only when `pyproject.toml` or `uv.lock` changes.

## Run in production

1. Make the env file and put real values in it:

   ```bash
   cp .env.prod.example .env.prod
   ```

2. Start:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

Put Nginx in front of port 8000 for HTTPS. The prod model needs a server with 16 GB RAM or more.

## Settings

| File | Use |
| --- | --- |
| `.env.example` | Template for dev. Copy to `.env.dev` |
| `.env.prod.example` | Template for prod. Copy to `.env.prod` |
| `.env.dev`, `.env.prod` | Real values. Not in Git |

The settings module is `config.settings.dev` or `config.settings.prod`.

## Development tools

```bash
uv sync                         # install packages
uv add <package>                # add a package
uv add --group dev <package>    # add a dev package
uv run ruff check --fix .       # lint (rules: see [tool.ruff] in pyproject.toml)
uv run ruff format .            # format
uv run ty check                 # type check
uv run pytest                   # test (a warning fails the run)
uv run pre-commit install       # turn on commit hooks (ruff, ruff format, ty)
```

Code standards:

- Docstrings use the Google style. Every public module, class, function, and method in `apps/`
  (except tests) has one. The first line is a short summary that ends with a period.
- A comment explains why the code does something. It does not repeat what the code does.
- Fix the cause of a ruff or ty message. Use a `# noqa: CODE` or `# ty: ignore[rule]` comment only
  when the code is correct, and always give the reason after it.
- ruff and ty must report no errors. The commit hooks run both.
