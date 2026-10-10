---
title: Docusaurus site and API reference generation
---

# Docusaurus site and API reference generation

## Source layout

- `docs/docs/` contains curated conceptual and operational pages.
- `docs/docusaurus.config.js` defines the site URL, `/docs/` base path, navigation, and theme.
- `docs/sidebars.js` defines the guide sections and includes the generated reference.
- `docs/scripts/generate_api_reference.py` scans the Python source with `ast`; it does not import application modules or connect to services.
- `docs/docs/reference/generated/` is generated output. Do not edit it by hand.
- `docs/Dockerfile` generates API pages, builds Docusaurus, and copies only static assets into an Nginx runtime image.
- `docs/nginx.conf` serves static content on the private port 8080 and exposes an internal health check.

## Local editing

```bash
cd docs
npm install
npm start
```

`prestart` runs the API generator first. Edit Markdown under `docs/docs/`; keep page IDs in `sidebars.js` synchronized with the paths. The site uses a base URL of `/docs/`, because production Caddy strips that prefix before forwarding requests to Nginx.

Build a static site and preview it:

```bash
npm run build
npm run serve
```

## Function inventory

The generator reads ASTs rather than importing Python modules. This avoids starting Django, connecting to PostgreSQL/Redis, loading credentials, or executing task registration code. It includes production `.py` files under `apps/` and `config/`, plus `manage.py`; it excludes tests, migrations, virtual environments, generated static files, and cache directories. It records nested functions and class methods.

Each module page lists source definitions and extracted docstrings. The coverage report separates functions with detailed documentation from functions that need more detail. A source link points to the corresponding location in the repository's `main` branch. If the build is made from a different branch, use the path and line number as the source locator and open that branch instead.

## Deployment behavior

The container build runs the generator against the same source tree that is being built, builds static HTML/CSS/JavaScript, and serves the result with Nginx. The runtime container has no Python runtime, database credentials, Ollama dependency, or access to the application backend. It is attached to the proxy network only in production. Caddy routes `/docs/` to the docs container. It does not publish a new host port.

## Dependency updates

Direct Docusaurus dependencies are pinned in `package.json`. When updating them, regenerate and commit `package-lock.json` using a network-enabled development machine, then change the Docker build to use `npm ci` after a lock file has been added. The initial integration uses `npm install` because no lock file existed when this documentation site was introduced; do not treat a transitive dependency resolution as reproducible until a lock file is checked in.
