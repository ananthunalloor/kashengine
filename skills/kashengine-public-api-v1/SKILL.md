---
name: kashengine-public-api-v1
description: Change KashEngine's public versioned HTTP API (/api/v1, django-ninja) without breaking the contract. Use when adding endpoints or fields under apps/api/v1, updating docs/openapi/v1.json, the API version, or the API changelog.
---

# Public API v1 change

The public API is a contract. Inside `v1` you may only **add** things. Never remove, rename, or
change the type or meaning of a field or parameter. See `docs/docs/api/versioning.md`.

## Steps

1. Change the router in `apps/api/v1/<domain>.py` and schemas in `apps/api/v1/schemas.py`.
   - Describe every field with `Field(description=...)`.
   - The endpoint docstring is the public OpenAPI description: summary + body only, written for
     the API user, naming the required feature. No `Args:`/`Returns:` sections.
   - Errors use the shared error envelope with a stable `code` (`apps/api/errors.py`,
     `docs/docs/api/errors.md`). Respect pagination (`apps/api/pagination.py`) and rate limits.
2. Export the OpenAPI document:

   ```bash
   uv run python manage.py export_openapi --output docs/openapi/v1.json
   ```

3. Run the tests. `apps/api/tests/test_openapi.py` fails if the file is stale, an operation lacks
   a summary/description, or a response field lacks a description.

   ```bash
   uv run pytest apps/api/tests
   ```

4. Bump the minor version in `apps/api/versions.py` and add an entry to
   `docs/docs/api/changelog.md`.
5. CI runs `docs/scripts/openapi_compat.py` against `main`; a breaking change fails. Related tests:

   ```bash
   uv run pytest tests/test_docs_scripts.py
   ```

## Test what matters

Status and error `code` for each failure, headers, paging limits, `ETag`, auth (token missing,
revoked, or lacking the feature), and that no secret appears in responses or logs.
