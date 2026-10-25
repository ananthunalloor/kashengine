---
title: Security model
sidebar_label: Security
description: The controls that protect Kash Engine, layer by layer, and how to check them.
---

# Security model

Each layer has its own controls. A change in one layer must not weaken another layer.

## Network

Caddy is the only service that is open to the internet. In production it publishes ports 80
(TCP), 443 (TCP) and 443 (UDP, for HTTP/3). No other service publishes a port.

Four Docker networks keep the services apart (`docker-compose.prod.yml`):

| Network | Members | Route to the internet |
| --- | --- | --- |
| `edge` | `caddy` | Yes. Caddy needs it for certificates. |
| `proxy` | `caddy`, `web`, `docs` | No. The network is `internal`. |
| `backend` | `web`, `worker`, `beat`, `db`, `redis`, `silo`, `silo-init`, `ollama` | No. The network is `internal`. |
| `egress` | `worker`, `beat`, `ollama` | Yes. For news, quotes, Telegram and model downloads. |

The `docs` service has static files only. It has no secret, no database and no route to the
internet.

In development, Compose binds every port to `127.0.0.1`. Port 8000 goes to Django and skips
Caddy. Use it only to debug.

## Edge: Caddy

Caddy ends TLS. For a public domain it gets a certificate from Let's Encrypt. For `localhost` or an
IP address it uses its own CA. These are the controls in `deploy/caddy/Caddyfile`:

- The Caddy admin API is off (`admin off`).
- Slow clients are closed: header 10 s, body 30 s, write 60 s, idle 2 min.
- A request body is limited to 2 MB. Only the backup import path
  (`/api/app/ops/actions/backups/import/`, and `/ops/backups/import/` on the archive host) allows
  141 MiB. This includes the form overhead of a snapshot file.
- Responses use `zstd` and `gzip`. Logs go to stdout as JSON.
- Caddy replaces the `X-Forwarded-*` headers of the client. Django trusts
  `X-Forwarded-Proto` only because of this (`SECURE_PROXY_SSL_HEADER`).
- Caddy adds `Permissions-Policy` and `Cross-Origin-Resource-Policy: same-origin`.
  Django adds HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and
  `Cross-Origin-Opener-Policy`.

### Route order

Caddy runs the `handle` blocks in the order written. The first match wins. The order is:

1. `/admin`, `/ops`, `/app/ops`, and `/api/app/ops` (including children) for an address outside `ADMIN_ALLOWED_IPS` get `403`.
2. `/docs` for an address outside `DOCS_ALLOWED_IPS` gets `403`.
3. `/docs` goes to `docs:8080`. Caddy does not remove the prefix.
4. Everything else goes to `web:8000`.

`tests/test_deploy_config.py` checks this order. It also runs the real `caddy` binary when the
binary is present.

### Content-Security-Policy

The main host (`SITE_ADDRESS`) uses this policy. Caddy sets it from `CSP_HEADER`:

```text
default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline';
img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self';
form-action 'self'; frame-ancestors 'none'
```

- Scripts come from the same origin only. There is no CDN and no `'unsafe-eval'`. The React
  bundle, the fonts and the styles are static files of the site.
- The live update stream and every API call use `connect-src 'self'`.
- Swagger UI at `/api/v1/docs` runs under this same policy. The files of Swagger UI are in
  `static/vendor/swagger-ui`. Its start code is in `static/js/swagger-init.js`, because inline
  scripts are not allowed.
- Do not add a new script host or `'unsafe-eval'` to fix a page. Find which file is blocked and
  serve it from the site.

The archive host (`OLD_SITE_ADDRESS`) keeps the older policy. It allows `https://cdn.jsdelivr.net`
and `'unsafe-eval'`, because the archived pages use Datastar. Only a superuser can open that
host, and it has `X-Robots-Tag: noindex, nofollow, noarchive`.

The docs site (`/docs/`) has its own policy. The `docs` service sets it. Docusaurus puts a few
small inline scripts in each page. The build step reads the page files and puts the hash of each
script in the policy (`docs/scripts/csp_hashes.py`). So the docs policy does not use
`'unsafe-inline'`. Caddy adds no policy for `/docs`, because a second policy would block the
first.

To test a new policy without blocking users, set
`CSP_HEADER=Content-Security-Policy-Report-Only`. The development override does this, because the
Django debug pages use inline styles.

## The archive host

The archived Django pages are available only on `OLD_SITE_ADDRESS` (for example
`old.example.com`). Three controls protect them:

- Caddy gives `403` to every address that is not in `ADMIN_ALLOWED_IPS`, for the whole host.
- `ArchiveMiddleware` selects the archive URL file only when the `Host` header matches. It then
  checks every resolved view. Only an active **superuser** can sign in there. A member or a staff
  user gets the normal "wrong login" answer, and the failure counts for `django-axes`.
- Every archive response is private and has `noindex` headers.

If you do not need the archive, do not publish a DNS record for the host.

## Containers

Every production service uses `no-new-privileges` and drops all Linux capabilities. `caddy` adds
`NET_BIND_SERVICE`. `db` and `redis` add the few capabilities that their entry points need to
set the owner of the data folder.

`web`, `worker`, `beat`, `caddy` and `docs` have a read-only root file system. They write only
to `/tmp` and to the named volumes. `web`, `worker` and `beat` run as the `app` user. The
`docs` service runs as the `nginx` user. Logs rotate: 10 MB each, 5 files.

## Access to the admin pages

`ADMIN_ALLOWED_IPS` limits `/admin/`, `/ops/`, `/app/ops/`, and `/api/app/ops/` at Caddy.
The value is a list of addresses and
ranges, separated by spaces. The default is everyone, so set it in production.

Test the address that Caddy sees from an allowed client and from a blocked client. Docker IPv6
and VPNs can change it.

The proxy rule is not the only guard. Django also checks who the user is. Only superusers can
change settings. Normal users never see configuration or infrastructure errors.

`DOCS_ALLOWED_IPS` has the same format. The docs do not contain secrets, but they describe the
system. Limit them in production.

## Sign-up and email verification

- **Invitations.** New accounts need a single-use invitation by default
  (`SIGNUP_INVITE_REQUIRED=true`). The code has 32 random bytes. The database keeps only its
  SHA-256 digest. A superuser makes a code in Django admin or on **Ops > Access > Invite codes**.
  The page shows the code one time. The audit trail records the number of the invitation, never
  the code. A code is used when the account is created, and not before.
- **Email verification.** The link holds a random token (32 bytes). The database keeps only its
  digest. A link ends after `EMAIL_VERIFICATION_HOURS` (24) and works one time. A new link
  replaces the old one. The resend button has a cooldown of one minute.
- **No features without a verified email.** A regular user can sign in, but all product features,
  the public API, token creation and linked Telegram reports stay locked until the email is
  verified. Staff and superusers are exempt. A superuser can mark an email verified in Django
  admin, only after the superuser confirms the ownership. The action is audited.
- **Terms.** The sign-up needs an agreement box. The version and the time are saved
  (`LegalAcceptance`) and cannot be changed in the admin.
- **A disabled account stays disabled.** Verification never turns on an account that an admin
  disabled.
- **No rate limit on `/signup/`.** The login limit of `django-axes` does not cover it. With
  `SIGNUP_INVITE_REQUIRED=false` anyone can create accounts and make the server send a
  verification email to any address. Keep invitations on, or add a limit at Caddy or in Django,
  before you open registration.

## Telegram webhook

Telegram calls `POST /api/telegram/webhook/` on the main host. The path is public and has no
CSRF check, so it has its own controls:

- The header `X-Telegram-Bot-Api-Secret-Token` must equal `TELEGRAM_WEBHOOK_SECRET`. The
  comparison takes constant time. If the secret is empty, every request gets `401`.
- The body is limited to 64 KiB and must be a JSON object.
- Only `/start <token>` in a **private** chat does something. The token is one time, ends after a
  short time, and the database keeps only its digest.
- The answer is `200` for an unknown token, so a caller cannot find out which tokens exist.
- A chat that is linked to another account is never moved.
- The chat ID is never returned by any API.

## Private application API

The React app calls `/api/app/`. These controls apply to it:

- It accepts a browser session only. A request with an `Authorization` header gets `401`.
- A request that changes data needs the CSRF token.
- Each user has `APP_API_RATE_LIMIT_PER_MINUTE` (300). The limit is separate from the public API.
- Answers have `Cache-Control: private, no-store`.
- `/api/app/ops/` paths need a **staff** session to read. A change needs a **superuser**. This
  includes **Stop** for a task run, which is also written to the audit trail.
- The live update streams (`/api/app/events` and `/api/app/ops/events`) send only the name of a
  changed part of the app. The staff stream also sends the id, label and status of a task run.
  They never send business data, task output, tracebacks or secrets. The server checks the
  session again each time a stream starts.
- A user without a verified email gets `403 email_verification_required` on every endpoint,
  except the Account and verification endpoints.
- A stream holds one Gunicorn thread for about 20 seconds. Many open streams can use all
  threads. Watch the thread count of `web`. See
  [Troubleshooting](./troubleshooting.md#the-app-is-slow-or-live-updates-stop).

## Login protection

`django-axes` counts failed logins for each client address.

- The limit and the lockout time are settings: `LOGIN_FAILURE_LIMIT` (5) and
  `LOGIN_COOLOFF_MINUTES` (30). `0` minutes means locked until an admin unlocks the address.
- A locked client gets a `429` page. The page does not show users or limits.
- A good login clears the failures (`AXES_RESET_ON_SUCCESS`).
- The client address is the first value of `X-Forwarded-For`, checked as an IP address. This is
  safe only because Caddy replaces the header.
- **Ops > Logins** shows the locked addresses. A superuser can unlock them.

## API security

- A token is `ke_<8 hex>_<48 hex>`. The database stores only a SHA-256 hash and the 8-character
  prefix. The full token is shown one time.
- A password change makes the old tokens invalid (`password_stamp`).
- Tokens expire after `API_TOKEN_EXPIRY_DAYS` (90). A user can have `API_TOKEN_MAX_PER_USER`
  (5) active tokens. The user or a superuser can revoke a token.
- The API has two rate limits. Each caller has `API_RATE_LIMIT_PER_MINUTE`. Each address has
  `API_AUTH_FAIL_LIMIT_PER_MINUTE` for failed token checks. The counters are in the Django cache
  (Redis, database 1, in production).
- The API follows the same access rules as the web app (subscription and feature rules).
- Answers have `Cache-Control: private` and `Vary: Authorization, Cookie`.
- The API has only `GET` endpoints. A request cannot change data.
- A superuser can turn the API off (`API_ENABLED`) or turn off only the Swagger page
  (`API_DOCS_ENABLED`).

See [Authentication](../api/authentication.md) and [Rate limits](../api/rate-limits.md).

## Secrets

- A secret saved on the dashboard (the Telegram bot token) is encrypted with Fernet. The key
  comes from `SETTINGS_ENCRYPTION_KEY`. If this is empty, the key comes from `DJANGO_SECRET_KEY`.
- The dashboard never shows a secret again. It shows only whether the secret is set.
- The audit trail records that a secret changed. It does not store the old or the new value.
- Log lines are cleaned before the Ops log viewer shows them (`redact()` in
  `apps/ops/logs.py`). It hides Telegram bot tokens, `token=`, `password=` and similar pairs,
  `Bearer` values, API tokens (`ke_...`) and session cookies.
- The `httpx` and `httpcore` loggers stay at `WARNING`. The `httpx` logger at `INFO` writes the
  full URL of each request. The Telegram URL contains the bot token.
- The Upstox access token is a saved secret too. It goes only in the `Authorization` header of
  a request to `api.upstox.com`. The client does not follow redirects, and no URL, header or
  provider error body goes in a log or an error text.
- The SMTP password (`EMAIL_HOST_PASSWORD`) and `TELEGRAM_WEBHOOK_SECRET` are environment
  values. Keep them in `.env.prod`.
- `.env.prod` is never in Git. Give it mode `600`.

## Audit

Each action of an admin on the Ops pages is written to the audit trail (**Ops > Audit**). An
event has the actor, the action, the target, a safe detail text, the client address and the time.
The `ops.prune` task deletes old history. It keeps task runs and login events for
`OPS_RETENTION_DAYS` (90 days). It keeps audit events for 365 days, or for
`OPS_RETENTION_DAYS` if that value is larger.

## Review checklist

Use this list for each change that touches security:

- [ ] No new public port in Compose.
- [ ] No secret in source, sample files, logs, task results, the audit trail or the docs.
- [ ] Authorization is tested for anonymous users, normal users and superusers.
- [ ] Invalid and large input is handled safely.
- [ ] New dependencies and image tags are reviewed.
- [ ] The CSP and the headers are tested through Caddy. No new script host and no `'unsafe-eval'`.
- [ ] A new live event holds no business data and no secret.
- [ ] A new public path (like the webhook) checks a secret, limits the body and returns the same
      answer for known and unknown values.
- [ ] A new route for signed-in users keeps the email-verification rule, unless it is meant for
      the Account page.
- [ ] A new `/api/app/ops/` change endpoint needs a superuser and writes an audit event.
- [ ] The read-only file system and the dropped capabilities still work.
- [ ] The backup and restore steps are still correct after a schema change.
