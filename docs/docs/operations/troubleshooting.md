---
title: Troubleshooting
---

# Troubleshooting

Use `docker compose ps` and per-service logs first. Avoid printing environment variables or full request URLs while diagnosing failures.

## The site or docs page is unavailable

```bash
docker compose ps
docker compose logs --tail=100 caddy web docs
```

Check whether the Caddy container is healthy, the `web` and `docs` health checks pass, and the expected Caddy routes are present. In development, confirm the ports are not already in use and that the browser accepts the local certificate. In production, verify DNS, host firewall rules, `SITE_ADDRESS`, and certificate issuance.

## The docs page loads without styles or scripts

The Docusaurus build uses `baseUrl: '/docs/'`, while Caddy strips `/docs` before forwarding to Nginx. If one changes without the other, asset requests can return 404. Inspect the browser network panel and ensure generated asset URLs begin with `/docs/`. Then validate the corresponding request path inside the docs container.

If the browser console reports CSP violations, identify the specific blocked resource. Do not fix the problem by broadly allowing `unsafe-inline`, wildcard origins, or untrusted scripts. Docusaurus should be self-hosted with same-origin assets.

## A documentation build fails

```bash
cd docs
npm install
npm run api:check
npm run build
```

`api:check` can fail because one or more source functions lack a sufficiently detailed docstring. This is a documentation quality failure, not necessarily a site compilation failure. Inspect the coverage report generated under `docs/docs/reference/generated/`, improve the source docstring, and regenerate the reference. For an MDX parse failure, inspect recent Markdown for unescaped angle brackets, braces, or JSX-like text.

## Celery task is late or not running

Check the worker and Beat logs, then inspect Ops > Jobs and Ops > Runs. Confirm the schedule is enabled and uses the intended time zone. The Beat schedule is database-backed, so editing an environment variable is not a substitute for changing the Ops schedule. Check the broker connection and whether a prior run is still active.

## News feed or provider data is stale

Inspect Ops > Feeds and the relevant task runs. Check the recorded fetch timestamp, last new-item count, and safe error value. A successful fetch with zero items differs from a failed provider request. Verify that the source is enabled and that the worker can reach the provider through its intended egress network.

## Telegram delivery fails

Inspect the delivery run and configuration status in Ops. Confirm the API address, bot token, and destination IDs without printing values to terminal logs. Verify that the outbound network path works and review HTTP status handling. Keep `httpx` at WARNING so a complete credential-bearing URL is not written to logs.

## A saved secret shows as not set

Check whether `SETTINGS_ENCRYPTION_KEY` changed. A different encryption key cannot decrypt the old value. Restore the correct key from the protected key store, or re-enter the secret through the superuser settings page. Do not dump the secret table to troubleshoot it.

## Login lockout

A repeated failure can result in an HTTP 429 lockout. Inspect Ops > Logins and unlock the affected address only after checking whether the failures are expected. Confirm the address observed through Caddy and the configured failure threshold/cooloff. Do not disable `django-axes` as a quick fix for a proxy address issue.
