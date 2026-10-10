---
title: Runtime configuration and secrets
---

# Runtime configuration and secrets

Runtime settings that are safe for the operator to change are registered in `apps/siteconfig/registry.py` and managed through the Ops dashboard. The registry defines the type, limits, group, and help text for each setting.

## Value precedence

The effective value order is:

1. A value saved in the database through Ops.
2. The corresponding environment variable.
3. The default in `config/settings/base.py` / the setting registry.

The settings layer caches effective values for five seconds. A dashboard edit therefore propagates to web, worker, and Beat processes without a restart after that short cache lifetime. If the database cannot be read, environment values provide the fallback.

Use the shared `conf` access layer (`conf.KEY`, `conf.get`, `conf.default`, `conf.is_saved`, `conf.overrides`, and `conf.invalidate`) rather than reading an overrideable setting directly from Django settings. Add a new setting to the registry with its validation, limits, group, description, default, and secret classification. Update `.env.example`, `.env.prod.example`, tests, and this page when a deployment variable changes.

## Which values belong in the registry?

Settings on the dashboard include Telegram, report sizing, LLM endpoint/model/timeouts, news, sentiment, market timing, IPOs, company refresh, health thresholds, login lockout limits, and web page size. The schedule, news feeds, and market instruments are separate database-managed records.

Values that can prevent the service from starting or that define the deployment boundary remain environment configuration, for example Django's secret key, database and Redis URLs, allowed hosts, trusted CSRF origins, security flags, and logging mode. Do not move sensitive infrastructure values into a form without a clear reason and a reviewed permission model.

## Secret lifecycle

Secret values are encrypted with Fernet. The encryption key is derived from `SETTINGS_ENCRYPTION_KEY`, or falls back to `DJANGO_SECRET_KEY` when the dedicated key is empty. A secret is not shown again after saving. An empty secret field keeps the saved secret. Audits record only that the secret changed.

Set a distinct `SETTINGS_ENCRYPTION_KEY` before rotating `DJANGO_SECRET_KEY`. If the encryption key changes, existing encrypted settings may become unreadable and the UI reports them as not set. In that situation, enter the secret again. Plan key rotation before the change and keep the key out of source control and logs.

## Changing the registry safely

1. Define the new `Spec` with a type, validation bounds, group, help text, default, and secret metadata as applicable.
2. Use the central accessor in all consumers.
3. Add tests for default, environment, database override, reset, invalid input, unchanged input, cache invalidation, and database failure behavior.
4. Confirm that audit events redact secrets.
5. Update the relevant Ops page and environment examples.
6. Run type checking, linting, migration checks, and the full test suite.
