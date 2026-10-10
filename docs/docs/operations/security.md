---
title: Security model
---

# Security model

Security controls apply across Docker, Caddy, Django, Celery, configuration, logging, and the Ops UI. A change to one layer must not weaken another layer unintentionally.

## Network exposure

- Caddy is the only service with published production ports: 80/TCP, 443/TCP, and 443/UDP for HTTP/3.
- `web`, `worker`, `beat`, PostgreSQL, Redis, Ollama, and the docs container have no published production ports.
- Caddy reaches the web app through the `proxy` network and the docs container through that same proxy network.
- Database and broker services remain on the internal backend network. Only services that need outbound provider access join `egress`.
- The docs image contains generated static output; it does not receive application environment secrets or connect to the database.

## Caddy and browser security

Caddy terminates TLS, redirects HTTP to HTTPS for a public domain, adds content security and other security headers, limits request-body size, closes slow connections, and has its administrative API disabled. Django sets the remaining application security headers and secure-cookie behavior. Keep policy changes narrow and test them in report-only mode before enforcing them.

The application retains the stricter CSP. Docusaurus classic injects a small inline script for its theme selection, so only the `/docs/` path uses a separate policy that permits inline scripts. That exception is limited to the static documentation origin; generated API docstrings escape JSX-sensitive characters and the site must not execute user-submitted content. Keep all JS, CSS, and fonts same-origin. Do not add third-party scripts, analytics, external fonts, or plugins without a security review. The dev override uses report-only mode for both policies.

## Container hardening

Production services use `no-new-privileges`, drop Linux capabilities, and use rotated logs. The application and edge containers use read-only root filesystems with explicit writable temporary or data volumes where needed. The Nginx docs container listens on 8080 and uses `/tmp` for writable temporary state. Do not add a published docs port.

## Admin access

`ADMIN_ALLOWED_IPS` limits `/admin/` and `/ops/` at the proxy. Test the address Caddy observes from an allowed and blocked client, especially when Docker IPv6 or a VPN is involved. Django view authorization remains required even when the proxy restriction is configured.

## Authentication and audit

`django-axes` limits failed login attempts and provides an HTTP 429 lockout response. Ops displays locked addresses and allows superusers to unlock them. Test that successful logins clear failures according to policy and that the client address is derived from the trusted proxy header, not an untrusted value supplied directly by a client.

Audit every privileged mutation. Store old and new values only when they are safe to retain. For secrets, record that a change occurred without storing either value. Never log the Telegram token or a full request URL that contains it.

## Security review checklist

- [ ] No new public Compose port.
- [ ] No secret in source, sample config, logs, task result, audit trail, or docs output.
- [ ] Authorization tested for all user classes.
- [ ] Invalid and oversized input handled safely.
- [ ] Dependencies and image tags reviewed.
- [ ] CSP and headers tested through Caddy.
- [ ] Read-only and capability-drop assumptions still hold.
- [ ] Backup and restore procedure remains valid after schema changes.
