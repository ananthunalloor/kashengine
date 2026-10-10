---
title: Testing and quality gates
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

For a production settings check, use a complete production-like environment with `DATABASE_URL`, `REDIS_URL`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` configured:

```bash
uv run python manage.py check --deploy --settings=config.settings.prod
```

Do not run the production check against incomplete placeholder configuration and interpret its errors as application defects. Do not put real credentials in shell history or documentation examples.

## Test boundaries

- Unit tests cover deterministic parsing, scoring, validation, settings resolution, and schedule calculations without requiring live services.
- Database tests use the explicit database marker/fixture convention in the existing suite.
- Task tests assert success and failure outcomes, not just that a task was called.
- HTTP-client tests mock external providers and assert timeouts, request parameters, and safe logging behavior.
- Authorization tests cover anonymous, ordinary, staff, and superuser users for sensitive Ops endpoints.
- Secret tests assert that raw values are not returned, logged, audited, or included in exception messages.
- Scheduling tests cover enabled and disabled entries, time-zone conversion, next-run calculations, missed runs, and grace periods.
- Browser tests should check navigation, mobile layout, JavaScript errors, and the production security headers where the test environment supports them.

## When a test fails

1. Reproduce the failure in isolation.
2. Decide whether the test exposed a code defect, an incorrect expectation, an environment problem, or a flaky external dependency.
3. Fix the cause. Do not loosen global warning filters or remove assertions only to make the suite green.
4. Add a focused regression test if the failure could recur.
5. Rerun the focused test and the full required check set.

## Documentation checks

From `docs/`:

```bash
npm install
npm run api:check
npm run build
```

`api:check` is intentionally strict. It reports source functions that lack a docstring or lack enough structure to be considered detailed documentation. Some existing functions may need follow-up documentation work before this gate passes; normal site generation still includes those functions and marks their documentation status in the coverage report.
