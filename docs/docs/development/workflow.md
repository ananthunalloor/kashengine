---
title: Development workflow and code layout
---

# Development workflow and code layout

## Keep domain logic in the owning app

Place a rule beside the data it governs. News parsing belongs with news; market direction logic belongs with markets; IPO scoring belongs with IPOs; settings validation belongs with siteconfig; operational controls belong with Ops. Avoid imports that make low-level domain apps depend on web views.

A typical request path should be thin:

1. A view validates input and checks access.
2. A form or service validates domain rules.
3. A service or model operation applies the change.
4. A task handles work that can take a long time.
5. Templates render safe output and do not recompute domain decisions.

Use the established module conventions in the app before adding a new abstraction. Keep public helper interfaces stable when more than one app or task uses them.

## Change checklist

- Find the relevant model, service, task, view, form, template, settings entry, and tests.
- Record the expected behavior before editing.
- Add validation at the boundary and enforce concurrent invariants in the database where appropriate.
- Keep external calls behind a small, testable boundary. Set timeouts and handle provider errors explicitly.
- Document parameters, returns, raised exceptions, side effects, transactions, retries, and security requirements for every function.
- Add tests for valid input, invalid input, edge cases, and failure behavior.
- If an environment setting changes, update its example environment file and the settings documentation.
- If an operator needs to tune a value, check whether it belongs in the siteconfig registry rather than being hard-coded.
- If an Ops action can send a message, overwrite data, or otherwise cause a side effect, require the established confirmation and authorization pattern.
- Run the checks below and review the final patch.

## Python checks

Run from the repository root:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

Tests run with warnings treated as errors. The test configuration uses `config.settings.dev`. Tests that touch the database must opt into the project's database test convention; do not allow a unit test to access the database by accident.

## Database migrations

- Make schema changes in model code and create a migration.
- Review generated migration operations and dependencies. Do not edit historical migrations just to improve new code.
- Keep seed migrations deterministic and safe to run once on a new database.
- Run the migration drift check and the relevant database tests.
- Before deployment, take a restorable backup and define the rollback or forward-fix plan.

## Patch delivery

When sharing work as a patch, generate it from a known base commit. State the base commit and the apply command. Do not combine unrelated changes. Verify the patch with `git apply --check` against the recipient's checkout before applying it.
