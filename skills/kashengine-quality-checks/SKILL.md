---
name: kashengine-quality-checks
description: Run and interpret KashEngine's test suites and quality gates (pytest, Ruff, ty, migrations check, Vitest, oxfmt, OpenAPI checks, docs build) and debug failing tests. Use before committing, when CI fails, or when deciding what tests to write.
---

# KashEngine quality checks

Source of truth: `docs/docs/development/testing.md` and `.github/workflows/ci.yml`.

## Python (repo root)

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest                     # or: uv run pytest apps/<app> -k <name>
```

- pytest uses `config.settings.dev`, SQLite, `--strict-markers`, and **warnings are errors**.
- Ruff: line length 100; rules include `D` (Google docstrings), `S`, `DTZ` (aware datetimes),
  `PL`, `TRY`, `C90`. Tests are exempt from `D`, `S101`, `PLR2004`, `ARG`, `SLF001`.
- Pre-commit runs Ruff, file checks, and `ty` on commit.

## Frontend (`frontend/`)

```bash
pnpm install --frozen-lockfile
pnpm format:check     # oxfmt
pnpm api:check        # generated client matches frontend/openapi/app.json
pnpm typecheck
pnpm test             # Vitest + Testing Library
pnpm build
```

## Docs (`docs/`)

```bash
npm run reference:check   # docstring contract
npm run build             # broken links/anchors/MDX errors fail
```

## Contracts

- Private API changed: `uv run python manage.py export_openapi --api app --output frontend/openapi/app.json`,
  then `pnpm --dir frontend api:generate`.
- Public API changed: `uv run python manage.py export_openapi --output docs/openapi/v1.json`.

## Where tests live

| Place | What |
| --- | --- |
| `apps/<app>/tests/` | Per-app tests |
| `apps/api/tests/` | Tokens, auth, rate limit, endpoints, middleware, live updates, both OpenAPI contracts |
| `frontend/src/**/*.test.tsx` | React app |
| `tests/test_deploy_config.py` | Compose files and Caddyfile |
| `tests/test_docs_scripts.py` | OpenAPI compatibility check |
| `tests/test_docgen.py` | Docstring parser, contract, baseline gate |

## What to test

- Parsing, scoring, validation, settings precedence, schedules: pure unit tests, no live services.
- Tasks: assert result and failure, not just that the task was called.
- HTTP clients: replace the provider; assert timeout, parameters, and that logs hold no secret.
- Access: anonymous, normal user, user without the feature, staff, superuser.
- Secrets: not returned, logged, audited, or present in exception messages.
- Schedules: enabled/disabled, time zones, next run, missed runs, grace periods.
- API: status and error `code`, headers, paging limits, `ETag`.

## When a test fails

1. Run it alone.
2. Classify: code defect, wrong expectation, environment, or unstable external service.
3. Fix the cause. **Never** delete an assertion or add a warning filter to pass.
4. Add a regression test.
5. Re-run the full checks.

Production-settings sanity check (needs a full prod-like env; placeholder errors are not code
defects):

```bash
uv run python manage.py check --deploy --settings=config.settings.prod
```
