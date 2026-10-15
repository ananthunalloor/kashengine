---
title: Troubleshooting
sidebar_label: Troubleshooting
description: Causes and fixes for the common faults in Kash Engine, the API and the documentation site.
---

# Troubleshooting

Start with the state of the services and with **Ops > Overview**. The overview shows the checks
for the database, Redis, workers, Beat, the LLM server, Telegram, disk, memory and migrations.

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml ps

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 caddy web docs
```

In development, use `docker compose ps` and `docker compose logs`. Do not print environment
variables or full request URLs when you look for a fault. They can contain secrets.

## The site is not available

1. Look at `docker compose ps`. `caddy` starts only after `web` and `docs` are healthy. If one of
   them is not healthy, read its log.
2. In production, check the DNS record, the firewall (TCP 80 and 443, UDP 443), `SITE_ADDRESS`
   and the certificate. Caddy logs the certificate steps.
3. In development, check that ports 80 and 443 are free. If they are not, change the `ports` of
   `caddy` in `docker-compose.override.yml`.
4. A `400` from Django usually means that the host name is not in `DJANGO_ALLOWED_HOSTS`. A `403`
   on a form post usually means that the origin is not in `DJANGO_CSRF_TRUSTED_ORIGINS`.

## `/admin/`, `/ops/` or `/docs/` returns 403 "Forbidden"

Caddy returned it. The client address is not in `ADMIN_ALLOWED_IPS` (for `/admin/` and `/ops/`) or
in `DOCS_ALLOWED_IPS` (for `/docs/`). Check the address that Caddy sees in the Caddy log
(`remote_ip`). With Docker and IPv6 it can be the address of the Docker gateway. Change the
value in `.env.prod` and recreate `caddy`.

## The docs page loads without style or scripts

- The site is built for `/docs/` and nginx serves it from `/docs/`. Caddy must **not** remove the
  prefix. If the Caddy route has `uri strip_prefix`, remove it. The browser network panel must
  show asset requests like `/docs/assets/...` with status 200.
- If the console shows CSP violations, read which file is blocked. Do not add `'unsafe-inline'` or a
  wildcard. The docs policy comes from the build (`docs/scripts/csp_hashes.py`) and lists the hash of
  each inline script. A new inline script needs a new build.
- A second `Content-Security-Policy` header from Caddy blocks the docs site. The Caddyfile must not add
  one for `/docs`.

## The application page is blank or Datastar does not work

Open the browser console. A CSP message shows the blocked source. The default policy allows
scripts from `'self'` and `https://cdn.jsdelivr.net`. If you set `DATASTAR_SRC` to another host,
add it to `script-src` in `deploy/caddy/Caddyfile`. To test a change, set
`CSP_HEADER=Content-Security-Policy-Report-Only` and recreate `caddy`.

## A documentation build fails

```bash
cd docs
npm ci
npm run reference:check
npm run build
```

| Message | Cause | Fix |
| --- | --- | --- |
| `reference:check` lists findings | A docstring breaks the [docstring standard](../development/docstring-standard.md) | Fix the docstring in the source file |
| `docs/openapi/v1.json` is missing or old | The API changed and nobody exported the file | `python manage.py export_openapi --output docs/openapi/v1.json`, then commit it |
| MDX compile error | `<`, `>`, `{` or `}` in plain text | Put the text in backticks |
| Broken link or anchor | A page moved or a heading changed | Fix the link. The build stops on it. |
| `npm ci` fails | `package.json` and `package-lock.json` differ | Run `npm install` once, then commit the lock file |

## The API returns an error

Each error is `application/problem+json` with a `code`. See [Errors](../api/errors.md).

| Status and code | Usual cause |
| --- | --- |
| `401 unauthenticated` or `invalid_token` | No token, a wrong token, a revoked token or a changed password |
| `401 token_expired` | The token is older than `API_TOKEN_EXPIRY_DAYS`. Make a new one on the Account page. |
| `403 subscription_required` or `feature_not_available` | The user has no subscription or no right to the feature (same rules as the web app) |
| `429 rate_limited` | Too many requests. Wait for `Retry-After` seconds. |
| `503 api_disabled` | A superuser set `API_ENABLED` to false on **Ops > Settings > REST API** |

If the rate limit seems wrong, remember that the counters are in the Django cache. In
production this is Redis database 1. If Redis is down, the API cannot count. Check the Redis
check on **Ops > Overview**.

The Swagger page at `/api/v1/docs` needs a login. It returns `404` when `API_DOCS_ENABLED` is
false.

## A Celery job is late or does not run

1. Check **Ops > Overview** for the workers and Beat.
2. Read the `worker` and `beat` logs.
3. Open **Ops > Jobs** and **Ops > Runs**. A run that never started shows "The job never started. Is
   a worker running?". The `ops.prune` task marks it after 2 hours.
4. Open **Ops > Schedule**. The schedule is in the database. A change in the environment file does
   not change it. Check that the entry is on and that the time zone is the one you want.
5. Check the Redis connection (`REDIS_URL`).

## News or other data is old

Open **Ops > Feeds** and the runs of the job. A fetch that succeeds with no new items is not a
failure. A failure shows a safe error text. Check that the source is on and that `worker` has a
route to the internet (the `egress` network).

Some sources are off by default (`IPO_FETCH_ENABLED`, `IPO_GMP_ENABLED`, `SCREENER_ENABLED`). Read
the note at the top of the matching source file before you turn one on.

## Telegram delivery fails

Look at **Ops > Overview** (Telegram) and the delivery run. Check the bot token and the chat IDs
on **Ops > Settings**. To list the chats that wrote to the bot:

```bash
docker compose exec web python manage.py telegram_check
```

Keep the `httpx` logger at `WARNING`. At a lower level it writes the full request URL, and the
Telegram URL contains the bot token.

## The LLM is slow or fails

Check that the model is downloaded (`ollama pull <model>`), that `LLM_BASE_URL` and `LLM_MODEL` are
right and that the host has enough RAM. Run `python manage.py llm_check`. A long text can pass
`LLM_TIMEOUT_SECONDS`.

## A saved secret shows as "not set"

The encryption key changed. The old value cannot be read. Enter the secret again on
**Ops > Settings**. See [Backups and recovery](./backups-and-recovery.md#recovery-notes).

## A user is locked out

After `LOGIN_FAILURE_LIMIT` failed logins from one address, the user gets a `429` page. Open
**Ops > Logins**. Find out why the logins failed, then unlock the address. If a whole office is
locked, check that the client address that Django sees is the real one. Do not turn off
`django-axes` to fix an address problem.
