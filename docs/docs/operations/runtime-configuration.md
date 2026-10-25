---
title: Runtime settings and secrets
sidebar_label: Runtime settings
description: Which settings a superuser can change on the dashboard, their order of precedence, and how secrets are stored.
---

# Runtime settings and secrets

The full list is in [Settings and environment variables](../reference/generated/system/settings.md).
That page is generated from the registry, so it is always current.

## Two kinds of values

| Kind | Where | Change |
| --- | --- | --- |
| **Dashboard setting** | `apps/siteconfig/registry.py` (a `Spec`: type, limits, group, help). | A superuser changes it on **Ops > Settings**. It takes effect in a few seconds with no restart. |
| **Environment variable** | `.env.dev`, `.env.prod`, `config/settings/*.py`. | Change the file and restart the services. |

Values that decide how the process starts stay in the environment: `DJANGO_SECRET_KEY`,
`DATABASE_URL`, `REDIS_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, the security
flags and the log mode. The schedule, the news feeds and the market instruments are rows in the
database, and have their own Ops pages.

## Order of values

For a dashboard setting, the value is, in this order:

1. The value that a superuser saved on the dashboard (the database).
2. The environment variable.
3. The default in `config/settings/base.py`.

Code reads a value with `conf`:

```python
from apps.siteconfig import conf

conf.LLM_MODEL  # the dashboard value, else the environment
conf.get("LLM_MODEL")  # the same
```

Each process (web, worker, beat) keeps the saved values in memory for 5 seconds
(`CACHE_SECONDS`). A change is live at once in the process that saved it. The other processes see
it in 5 seconds or less. If the database cannot answer, `conf` uses the environment values.

Do not read an overrideable setting from `django.conf.settings` in the application code.

## Validation

The form is built from the registry. Each type has rules:

| Type | Rule |
| --- | --- |
| `int`, `float` | A number inside `minimum` and `maximum`. |
| `bool` | On or off. |
| `str` | A text. |
| `url`, `urls` | `http` or `https` with a host. |
| `list` | One item for each line. Each item must match the pattern of the setting (for example a chat id). |
| `clock` | `HH:MM`, 24-hour. |
| `secret` | A text. It is encrypted before it is saved. |

An invalid value is not saved. The page shows the reason.

## Secrets

A secret (the Telegram bot token and the Upstox access token) is **encrypted with Fernet** before it goes in the database.

- The key comes from `SETTINGS_ENCRYPTION_KEY`. If that is empty, it comes from `DJANGO_SECRET_KEY`.
- The page never shows a saved secret. It shows only whether one is set. An empty field keeps the
  saved secret.
- The audit trail says that a secret changed. It never holds the old or the new value.
- Logs and the log viewer hide tokens.
- If the key changes, the old secrets cannot be read. They count as "not set". A superuser must
  enter them again.

:::important
Set a separate `SETTINGS_ENCRYPTION_KEY` **before** you rotate `DJANGO_SECRET_KEY`. Keep both keys
out of Git and out of logs, and back them up apart from the database.
:::

## Add a setting

1. Add a `Spec` to the registry with a type, limits, a group and a help text.
2. Add its environment default to `config/settings/base.py` (`env.int("NAME", default=...)`).
3. Read it with `conf.NAME` everywhere.
4. Add the line to `.env.example` and `.env.prod.example`.
5. Write tests for the default, the environment, the saved value, the reset, an invalid value,
   an unchanged secret, the cache and a database failure.
6. Run the checks. The generated settings page changes by itself.
