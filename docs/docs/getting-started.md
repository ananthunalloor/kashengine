---
title: Getting started
sidebar_label: Getting started
description: Run Kash Engine on your computer, make an admin user, and run the checks.
---

# Getting started

## What you need

| Tool | Use |
| --- | --- |
| Git | Source control. |
| Docker Engine and the Docker Compose plugin | Run the whole stack (Django, Celery, PostgreSQL, Redis, Ollama, Caddy, docs). |
| Python 3.13 and [`uv`](https://docs.astral.sh/uv/) | Run the checks and the tests outside Docker. |
| Node.js 20 or later and npm | Work on the documentation site or on the Tailwind CSS outside Docker. |

The versions are in `pyproject.toml`, `uv.lock` and `docs/package-lock.json`. Do not change a
dependency without changing its lock file and running all checks.

## Start the stack

```bash
cp .env.example .env.dev
docker compose up --build
```

Docker Compose loads `docker-compose.override.yml` for development. It starts the services
with file watching: Django reloads when a `.py` file changes, and the Celery worker and beat
restart too. Rebuild only when `pyproject.toml` or `uv.lock` changes.

| Address | What |
| --- | --- |
| `https://localhost/` | The web app, through Caddy. |
| `https://localhost/docs/` | This documentation. |
| `https://localhost/api/v1/docs` | Swagger UI (sign in first). |
| `localhost:8000` | Django without Caddy. Use it only to debug. |
| `localhost:5432`, `localhost:11434` | PostgreSQL, Ollama. |

Caddy signs the development certificate with its own local certificate authority. The browser
shows a warning until you trust that authority (see the README).

In development the Content-Security-Policy is report only. The browser console shows each
violation, and nothing is blocked.

Make an admin user, and download the development model:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec ollama ollama pull llama3.2:3b
```

The model name is the setting `LLM_MODEL`. Production uses a larger model. See
[Self-hosting](./operations/self-hosting.md).

## Run the checks

Run these commands from the repository root. All of them must pass before you share a change.

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

The tests run with warnings as errors, with the settings `config.settings.dev` and a SQLite
database. See [Testing](./development/testing.md).

## Work on the documentation

```bash
cd docs
npm ci
npm start                    # make the generated pages, then start the site on port 3000
npm run build                # make the pages and build the static site
npm run reference:check      # fail when a docstring does not meet the standard
```

## Change the code

1. Read the module, its tests and its page in the [Python reference](./reference/generated/python/index.md).
2. Make one change that has one purpose.
3. Write tests for the normal case, the errors and the limits.
4. Write the docstrings. Update the guide page if the behavior changed.
5. If you changed the API, export the OpenAPI file (see [Versioning](./api/versioning.md)).
6. Run the checks.
7. Read `git diff`. Look at settings, migrations, secrets and deployment files with extra care.

See the [development workflow](./development/workflow.md) for the full list.
