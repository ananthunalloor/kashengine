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

## `/admin/`, `/ops/`, `/api/app/ops/` or `/docs/` returns 403 "Forbidden"

Caddy returned it. The client address is not in `ADMIN_ALLOWED_IPS`
(for `/admin/`, `/ops/`, `/app/ops/`, and `/api/app/ops/`) or
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

## The application page is blank

Open the browser console and the network panel.

- **A CSP message.** It shows the blocked source. The main policy allows scripts from `'self'`
  only. Do not add a CDN or `'unsafe-eval'`. Serve the file from the site. To test a change, set
  `CSP_HEADER=Content-Security-Policy-Report-Only` and recreate `caddy`.
- **Django shows an error about the Vite manifest.** The React app is not built. In production,
  rebuild the image (`up -d --build web`). The `Dockerfile` builds `frontend/dist`. For a local run
  without Docker, run `pnpm build` in `frontend/`.
- **In development the page is blank and port 5173 does not answer.** The `frontend` service is
  not running or `DJANGO_VITE_DEV_MODE` is off. Check `docker compose logs frontend`.

## The archive host does not work

The archived Django interface is at `OLD_SITE_ADDRESS`. If it fails:

1. Check that the host name has a DNS record and is in `DJANGO_ALLOWED_HOSTS` and
   `DJANGO_CSRF_TRUSTED_ORIGINS`. A `400` means the host name is not allowed.
2. Only a superuser can sign in. A staff or member account always gets "wrong login".
3. A `403` "Forbidden" from Caddy means the address is not in `ADMIN_ALLOWED_IPS`. The whole
   archive host uses this rule.

## The app is slow or live updates stop

The app refreshes with a live update stream (`/api/app/events`). Each open tab holds one Gunicorn
thread. `web` has 3 workers with 16 threads each, so about 48 streams fill all threads. Then
normal requests wait.

1. Count the open streams: look for repeated requests to `/api/app/events` in the Caddy log.
2. Raise `--threads` in `docker-compose.prod.yml` for `web`, and check the connection limit of
   PostgreSQL. Each stream reads the database one time each second.
3. Check that no proxy buffers the stream. Django sends `X-Accel-Buffering: no`. A stream
   that shows no events until it ends is buffered.
4. If the app does not refresh, but the page works, reload it. The app asks for a full refresh
   when it was away too long. The `ops.prune` task deletes live events after one day.
5. A change that is made outside a task and outside a model save (a bulk write) sends no event.
   The code must call `apps.api.live.publish("all")` after it. Use **Refresh** in the app.

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

## A user cannot use the app after sign-up

A new account can sign in, but a regular user sees only **Account** until the email is verified.

1. Ask the user to open **Account** and select **Send verification email**. The link ends after
   `EMAIL_VERIFICATION_HOURS` (24) and works one time. The button waits one minute between sends.
2. If no email arrives, check the SMTP values (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`,
   `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`) and the `web` log. A failed send
   is logged as a warning, and the Account API answers `503 email_delivery_failed`. The account
   exists in this case.
3. If you cannot fix the email, a superuser can mark the email verified in **Django admin >
   Users** (action **Mark email verified**). Confirm the ownership first.
4. An existing account with no email address needs an address from an administrator first.
5. A sign-up that says "invite code is invalid" used a code that is wrong, revoked or already used.
   Make a new code on **Ops > Access > Invite codes**.

## Telegram linking does not work

1. Check `TELEGRAM_BOT_USERNAME` and `TELEGRAM_WEBHOOK_SECRET`.
2. The webhook of the bot must be `https://<SITE_ADDRESS>/api/telegram/webhook/`, with the same
   secret token. Do not use `getUpdates` while a webhook is set.
3. A wrong secret gives `401`. A user with no verified email gets `403` and the link stays.
4. The user must send `/start <code>` to the bot in a private chat. The code ends after a short
   time. Make a new link on **Account**.

## Upstox data is missing or old

1. Check that `UPSTOX_ENABLED` is on and the token is set (**Ops > Settings > Markets and prediction**). The
   tasks skip all calls when Upstox is off. A token that expired gives an error text for each
   company. Save a new token. The code does not renew it.
2. A company needs an exact instrument key in Django admin. Prices, fundamentals and company news
   need it.
3. Look at **Ops > Runs** for `markets.upstox_quotes` and `markets.upstox_refresh`. Quotes are
   saved only in a trading session. Check the [trading calendar](../domains/markets-and-predictions.md#the-trading-calendar).
4. The page `/markets/live` shows the error of each company.
5. Live prices come from the `streamer` service. Read its log: `docker compose logs streamer`.
   It retries forever, so a new token or mapping is used at the next connect.
6. If the Today page shows "Connecting" or "Reconnecting" all the time, check the `realtime`
   service (`docker compose logs realtime`) and that Caddy routes `/ws/*` to it. A socket closed
   with code 4403 means the account has no Markets access.

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
