---
title: Function documentation standard
---

# Function documentation standard

Every production Python function, method, nested helper, task, view, signal receiver, form clean method, model method, and management-command entry point must have a useful docstring. A one-line restatement of the function name is not sufficient. The goal is to explain the contract so another developer can safely change the implementation.

## Required content

For each function, document the relevant items below. Include a section only when it adds information, but do not omit information needed to call or change the function safely.

1. **Purpose and behavior:** what the function does, why it exists, and the boundary of its responsibility.
2. **Inputs:** each argument, accepted values, defaults, normalization, units, time zone, and whether the function mutates or retains the value.
3. **Return value:** exact type and meaning, including empty values, `None`, sentinels, partial results, and ordering guarantees.
4. **Exceptions:** exceptions that callers can expect, why they occur, and whether the caller should retry or display a safe error.
5. **Side effects:** database writes, transactions, cache invalidation, network calls, messages sent, files changed, or logs emitted.
6. **State and invariants:** required preconditions, uniqueness assumptions, locking, idempotency, and postconditions.
7. **Failure behavior:** timeout policy, retry policy, partial failure handling, and how failure is represented.
8. **Security:** authorization assumptions, sensitive fields, redaction requirements, and whether the function can reveal configuration or user data.
9. **Concurrency and time:** behavior under parallel calls, transaction boundaries, time-zone interpretation, and clock assumptions where relevant.
10. **Examples:** provide a short example for non-obvious public helpers and command/task entry points.

Do not document an implementation detail as a contract if callers must not depend on it. Update the docstring and tests in the same change when the contract changes.

## Google-style docstring template

The repository configures Ruff to use Google-style docstrings. Use this pattern and remove headings that are not relevant only when the omission is safe:

```python
def publish_report(report_date: date, *, dry_run: bool = False) -> DeliveryResult:
    """Publish a daily report to the configured Telegram destinations.

    Build the payload from the persisted report for ``report_date`` and send it
    to each enabled destination. A dry run validates and builds the payload but
    does not make a network request.

    Args:
        report_date: Trading/report date in the project's configured time zone.
        dry_run: If true, skip all external delivery and return the planned result.

    Returns:
        A result with one status for each destination. A successful return does
        not imply that every destination succeeded; inspect the per-destination
        statuses.

    Raises:
        Report.DoesNotExist: If no report exists for the requested date.
        ConfigurationError: If delivery is enabled but required settings are absent.

    Side effects:
        Sends HTTP requests unless ``dry_run`` is true. Never logs bot tokens or
        complete Telegram request URLs.

    Retry:
        The caller may retry transient provider failures. Do not retry permanent
        authorization errors without correcting the configuration.
    """
```

The function above is an illustrative template, not a claim that this exact function exists in the repository.

## Function-specific requirements

### Django views and forms

Document accepted request methods, validated form data, permission assumptions, redirect or response behavior, and safe error behavior. Do not duplicate template text in a docstring. State the access levels that may read or mutate data.

### Models and services

Document data invariants, whether the method saves the object, transaction behavior, validation expectations, cache invalidation, and exceptions caused by missing or stale data. State when database constraints are relied on for race safety.

### Celery tasks and scheduled jobs

Document task arguments, result shape, external providers used, retry/timeout policy, idempotency, duplicate-run protection, and operational signals that indicate success or failure. State whether a task is safe to invoke manually.

### HTTP clients and parsers

Document the provider, timeout, expected content shape, normalization rules, rate/size assumptions, and behavior for malformed data or status codes. Never include live credentials or unredacted URLs in examples.

### Settings and security helpers

Document value precedence, validation limits, cache lifetime, secret redaction, failure fallback, and whether changing a key invalidates saved encrypted values. Never expose a real setting value in generated API docs.

### Private and nested functions

Private functions are part of the maintained code and are included in the generated reference. Document them when their behavior is non-trivial, they encode business rules, or their failure semantics could affect a caller.

## Automatic inventory and enforcement

`npm run api:generate` scans Python source under `apps/`, `config/`, and `manage.py`. It creates a page per module with function signatures, source line links, source docstrings, and a coverage status. The generated coverage report identifies missing and short docstrings and checks for argument/return sections where those sections are expected.

Run `npm run api:check` to list functions that still need work. The API site can be built while the backlog is being addressed, but “listed” does not mean “fully documented.” The goal is to clear all `Needs detail` and `Missing` entries and keep that state clear in code review.
