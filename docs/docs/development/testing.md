---
title: Testing and quality gates
sidebar_label: Testing
description: How the tests are built, what each kind of test covers, and the checks that CI runs.
---

# Testing and quality gates

## Required checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

| Tool | Setting |
| --- | --- |
| pytest | `config.settings.dev`, test paths `apps` and `tests`, `--strict-markers`, **warnings are errors**. Tests use a SQLite database. |
| Ruff | Line length 100. Rules include `D` (Google docstrings), `S` (security), `DTZ` (aware datetimes), `PL`, `TRY` and `C90`. Tests are exempt from `D`, `S101`, `PLR2004`, `ARG` and `SLF001`. |
| ty | Type check with Python 3.13. |

A root `conftest.py` clears the settings cache before and after each test, because `conf` keeps
saved settings in memory for 5 seconds.

For a check of the production settings, give a complete production-like environment:

```bash
uv run python manage.py check --deploy --settings=config.settings.prod
```

Do not read errors from a check with placeholder values as defects of the code.

## Where the tests are

| Place | What |
| --- | --- |
| `apps/<app>/tests/` | Tests of one app. |
| `apps/api/tests/` | Tokens, authentication, rate limit, endpoints, middleware, and the OpenAPI file. |
| `tests/test_deploy_config.py` | The Compose files and the Caddyfile. A test that adapts the Caddyfile with the real Caddy runs only when `caddy` is on the `PATH`. |
| `tests/test_docs_scripts.py` | The OpenAPI compatibility check. |
| `tests/test_docgen.py` | The docstring parser, the contract checks, the baseline, and a gate test that runs the contract check on the whole repository. |

## What to test

- Parsing, scoring, validation, the order of settings, and schedule calculations: unit tests with
  no live service.
- Tasks: assert the result and the failure, not only that the task was called.
- HTTP clients: replace the provider. Assert the timeout, the parameters and that no log line
  holds a secret.
- Access: test an anonymous user, a normal user, a user without the feature, a staff user and a
  superuser for each Ops page and each API endpoint.
- Secrets: assert that a raw value is not returned, not logged, not audited and not in an
  exception message.
- Schedules: enabled and disabled entries, time zones, next run, missed runs and grace periods.
- The API: the status and the `code` of each error, the headers, the paging limits and the
  `ETag`.

## When a test fails

1. Run the test alone.
2. Decide: a defect in the code, a wrong expectation, a problem in the environment, or an
   unstable external service.
3. Fix the cause. Do not remove an assertion or a warning filter to make the suite pass.
4. Add a test for the failure.
5. Run the full set of checks again.

## Documentation checks

```bash
cd docs
npm run reference:check     # docstring contract
npm run build               # broken links, anchors and MDX errors fail the build
```
