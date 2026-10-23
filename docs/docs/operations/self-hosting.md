---
title: Self-hosting and deployment
sidebar_label: Self-hosting
description: How to run Kash Engine and this documentation site in development and in production with Docker Compose.
---

# Self-hosting and deployment

Docker Compose runs all services. Caddy is the only service that is open to the internet. The
documentation site is one of the services (`docs`). Caddy shows it at `https://<SITE_ADDRESS>/docs/`.

| Service | Job | Port inside Docker |
| --- | --- | --- |
| `caddy` | TLS, routing, headers | 80, 443 (published) |
| `web` | Django (gunicorn in production, `runserver` in development) | 8000 |
| `worker` | Celery worker | none |
| `beat` | Celery Beat. The schedule is in the database. | none |
| `db` | PostgreSQL 17 | 5432 |
| `redis` | Celery broker and Django cache | 6379 |
| `ollama` | Local LLM | 11434 |
| `docs` | nginx with the static documentation site | 8080 |

The `docs` service gets no Django, database, Redis or Telegram settings.

## Development

You need Docker and the Compose plugin.

```bash
cp .env.example .env.dev
docker compose up --build
```

Compose loads `docker-compose.override.yml` by itself. The override file:

- binds every port to `127.0.0.1`;
- sets `SITE_ADDRESS=localhost`, so Caddy makes a certificate with its own CA (the browser shows a
  warning the first time);
- sets the CSP to report-only;
- mounts the source tree and reloads `web`, `worker` and `beat` when a `.py` file changes.

Then:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec ollama ollama pull llama3.2:3b
```

Open `https://localhost/` for the app and `https://localhost/docs/` for these docs.

Rebuild only when `pyproject.toml` or `uv.lock` changes.

## Production

Use a Linux host with Docker Engine and the Compose plugin. The production model needs 16 GB of
RAM or more. The size depends on the model that you choose.

1. Point the DNS record of your domain to the server. Open TCP 80, TCP 443 and UDP 443.
2. Make the environment file and protect it:

   ```bash
   cp .env.prod.example .env.prod
   chmod 600 .env.prod
   ```

3. Set real values for `SITE_ADDRESS`, `ACME_EMAIL`, `DJANGO_ALLOWED_HOSTS`,
   `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` (and the same password
   in `DATABASE_URL`), and `TELEGRAM_BOT_TOKEN`. Keep `localhost` in `DJANGO_ALLOWED_HOSTS`:
   the Docker health check needs it. Set `ADMIN_ALLOWED_IPS` and `DOCS_ALLOWED_IPS`.
   Configure SMTP values, `TELEGRAM_BOT_USERNAME`, and a random
   `TELEGRAM_WEBHOOK_SECRET` if users should self-register and receive reports. Register
   `https://<SITE_ADDRESS>/api/telegram/webhook/` with Telegram as the bot webhook using that same
   secret token. Keep `SIGNUP_INVITE_REQUIRED=true` and generate single-use invitations in
   Django admin after creating your superuser. Review and adapt the starter Terms of Use and
   Privacy Notice at `/legal/` with qualified counsel and publish operator contact details before
   inviting users. See [Account sign-up](../domains/reports-and-delivery.md#account-sign-up-and-destinations).
   Do not commit `.env.prod`.
4. Start the stack. The `--env-file` option is required, because Compose reads `SITE_ADDRESS`
   and `ACME_EMAIL` from it:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     up -d --build
   ```

   The production file does not use the development override.
5. Make the first superuser and download the model:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec web python manage.py createsuperuser

   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec ollama ollama pull llama3.1:8b
   ```

6. Run the Django deployment check with the production settings. It must show no issues:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec web python manage.py check --deploy
   ```

7. Open `https://<SITE_ADDRESS>/`, `https://<SITE_ADDRESS>/docs/` and
   `https://<SITE_ADDRESS>/api/v1/docs`. Make sure that no file returns 404 and that the browser
   console shows no CSP violation.
8. Test the controls before you depend on the system: a login lockout, the
   `ADMIN_ALLOWED_IPS` rule from a blocked address, a report, Telegram delivery, the next run
   times on **Ops > Schedule**, a backup and a restore.

On start, `web` runs `migrate` and `collectstatic`, then starts gunicorn with 3 workers.

To test the production stack on your own computer, set `SITE_ADDRESS=localhost`.

## The documentation image

The image `docs/Dockerfile` has four stages:

1. `reference` reads the Python source (it does not run project code) and `docs/openapi/v1.json`.
   It writes the reference pages.
2. `site` runs `npm ci` with the lock file and builds Docusaurus.
3. `headers` reads the built pages and makes the Content-Security-Policy with the hash of each
   inline script.
4. `runtime` is nginx 1.28. It runs as the `nginx` user on port 8080 and serves the site from
   `/usr/share/nginx/html/docs/`.

The build needs the file `docs/openapi/v1.json` in the repository. After a change to the API,
export it first and commit it. A test checks that the file is current (see
[Documentation site](../development/documentation-site.md)).

The site is built for the path `/docs/` (`baseUrl`). nginx serves it from the same path, and
Caddy does **not** remove the prefix. If you change the path, change the Docusaurus `baseUrl`,
`docs/nginx.conf`, the Caddy routes and the tests together.

Build arguments (Compose passes them):

| Argument | Default | Use |
| --- | --- | --- |
| `DOCS_URL` | `https://${SITE_ADDRESS}` | The public URL. Docusaurus uses it for canonical links. |
| `DOCS_SOURCE_REF` | `main` | The Git ref in the source links of the Python reference pages. |

### Update only the documentation

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build docs
```

Add `caddy` to the command if you changed `deploy/caddy/Caddyfile`. Caddy reads its files from the
mounted folder, so restart it to load a new file.

### Check after a deploy

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml ps

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 web docs caddy
```

All services must be `healthy`. The health checks are:

| Service | Check |
| --- | --- |
| `web` | `GET http://localhost:8000/health/` returns `{"status": "ok"}` |
| `docs` | `GET http://127.0.0.1:8080/healthz` returns `ok` |
| `caddy` | `GET http://127.0.0.1:8081/healthz` (inside the container) |
| `db` | `pg_isready` |
| `redis` | `redis-cli ping` |

`caddy` starts only after `web` and `docs` are healthy.

### Roll back

Keep the Git revision that worked. To roll back, check out that revision and run the `up -d --build`
command again. If a build fails, Compose keeps the old container. Do not roll back a database
migration unless the migration supports it and you have a plan for the data that was written
after the deploy. Take a [backup](./backups-and-recovery.md) before each deploy that has a
migration.

## Volumes

| Volume | Holds | Keep? |
| --- | --- | --- |
| `postgres_data` | The database | Yes. Back it up. |
| `caddy_data` | TLS certificates and keys | Yes. Let's Encrypt limits new certificates. |
| `caddy_config` | Caddy autosave | No |
| `ollama_data` | Downloaded models | Optional. You can download them again. |
| `logs` | `app.log` (10 MB, 5 files) | Optional |
| `staticfiles` | The result of `collectstatic` | No. The `web` service makes it again. |

## Notes

- Docker changes the firewall rules itself. A tool such as `ufw` does not block a port that Docker
  publishes. This is why only Caddy has published ports.
- `ADMIN_ALLOWED_IPS` and `DOCS_ALLOWED_IPS` use the address that Caddy sees. With Docker and IPv6,
  this can be the address of the Docker gateway. Test from an allowed and from a blocked address.
- The API rate limit needs the Redis cache. In production, the cache URL is `CACHE_URL`. The
  default is the `REDIS_URL` with database `1`.
- Most settings are first values only. A superuser can change them on **Ops > Settings**. See
  [Runtime configuration](./runtime-configuration.md).

## Run the docs site without Docker

You need Node.js 22 and Python 3.13.

```bash
cd docs
npm ci
npm start             # development server at http://localhost:3000/docs/
npm run build         # production build in docs/build
npm run serve         # serve the build at http://localhost:8080/docs/
```

`npm start` and `npm run build` first make the reference pages (`npm run reference:generate`).
Do not bind the development server to an untrusted network.
