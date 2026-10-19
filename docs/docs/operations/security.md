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
| `backend` | `web`, `worker`, `beat`, `db`, `redis`, `ollama` | No. The network is `internal`. |
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
- A request body is limited to 2 MB.
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

The application pages use this policy. Caddy sets it from `CSP_HEADER`:

```text
default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval';
style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self';
connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
```

- `https://cdn.jsdelivr.net` is for the Datastar script. To serve the script from this site,
  save it as `static/vendor/datastar.js` and set `DATASTAR_SRC`.
- `'unsafe-eval'` is needed by Datastar to read expressions.
- Swagger UI at `/api/v1/docs` runs under this same policy. Its start code is in
  `static/js/swagger-init.js`, because inline scripts are not allowed.

The docs site (`/docs/`) has its own policy. The `docs` service sets it. Docusaurus puts a few
small inline scripts in each page. The build step reads the page files and puts the hash of each
script in the policy (`docs/scripts/csp_hashes.py`). So the docs policy does not use
`'unsafe-inline'`. Caddy adds no policy for `/docs`, because a second policy would block the
first.

To test a new policy without blocking users, set
`CSP_HEADER=Content-Security-Policy-Report-Only`. The development override does this, because the
Django debug pages use inline styles.

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
- [ ] The CSP and the headers are tested through Caddy.
- [ ] The read-only file system and the dropped capabilities still work.
- [ ] The backup and restore steps are still correct after a schema change.
