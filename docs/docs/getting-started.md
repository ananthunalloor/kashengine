---
title: Getting started
---

# Getting started

## Required tools

- Git.
- Docker Engine and the Docker Compose plugin.
- A system that can run the development Ollama model. The production model needs substantially more memory; the repository README currently recommends at least 16 GB for the production model.
- Python 3.13 and `uv` for running the project tools outside the containers.
- Node.js 20 or later and npm to edit or run the Docusaurus site outside Docker.

Use the versions declared by `pyproject.toml`, `uv.lock`, and `docs/package.json` as the project dependency contract. Do not update a runtime dependency without updating its lock or pin and running the full checks.

## Start the development stack

After applying the Git patch, integrate the new service with the current Compose and Caddy files. The script checks all required anchors before it writes any file and can be run again safely.

```bash
python docs/scripts/integrate_self_hosted_docs.py --check
python docs/scripts/integrate_self_hosted_docs.py
cp .env.example .env.dev
docker compose config --quiet
docker compose up --build
```

Compose loads `docker-compose.override.yml` for local development. Open `https://localhost/` for the application and `https://localhost/docs/` for developer documentation. Caddy uses a local CA in development, so a browser warning is expected until that CA is trusted. The development override binds published ports to `127.0.0.1`.

Create the Django superuser in a second terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

Download the development model:

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

The exact model name is deployment configuration. Check `.env.example` and `.env.prod.example` before changing it.

## Useful commands

```bash
# Run the Python checks from the repository root.
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest

# Work on the documentation site.
cd docs
npm install
npm start                 # Generate API pages and start the local site.
npm run build             # Generate API pages and validate the static build.
npm run serve             # Serve the built site locally.
npm run api:check         # Report functions that need more complete documentation.
```

The local Docusaurus server normally uses port 3000. The production container serves the same static build on its private port 8080; Caddy exposes it at `/docs/`.

## Change workflow

1. Read the relevant application module, its tests, and its existing API reference page.
2. Make one scoped change.
3. Add or update tests for normal behavior, errors, and boundary conditions.
4. Update detailed function docstrings and the relevant conceptual guide.
5. Run the Python checks and the documentation build.
6. Review `git diff`, especially settings, migrations, secret handling, and deployment files.
7. Send a patch file if you are sharing changes outside your own working clone.

See [the development workflow](./development/workflow.md) and [test guidance](./development/testing.md) for the full checklist.
