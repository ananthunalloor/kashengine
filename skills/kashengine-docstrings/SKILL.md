---
name: kashengine-docstrings
description: Write or fix Python docstrings in KashEngine to pass the docstring contract gate (Google style + ASD-STE100 Simplified Technical English, ratcheting baseline). Use when adding or changing any module, class, function, or method in apps/, config/, or manage.py, or when `npm run reference:check` fails.
---

# KashEngine docstrings

Source of truth: `docs/docs/development/docstring-standard.md`. CI fails on any new gap.

## Contract (checked mechanically)

| Definition | Requirement |
| --- | --- |
| Module / class | Summary line. |
| Function / method | Summary line. |
| With parameters | `Args:` listing **every** parameter by real name, and nothing else. |
| Non-`None` return | `Returns:` (or `Yields:` for generators). |
| Explicit `raise` | `Raises:`. |

Exempt: properties and dunder/nested functions need only a summary; one-statement no-arg
functions need no `Returns:`; Django `Meta` and `@overload` need nothing. **django-ninja route
functions** get summary + body only (it becomes the OpenAPI description); no `Args:`/`Returns:`.

## Section order

Summary, body, `Args:`, `Returns:`, `Raises:`, `Side effects:`, `Security:`, `Note:`,
`Example:`. Add a section only when it is true and useful.

```python
def next_after(cron: crontab, after: datetime) -> datetime:
    """Return the first run time of a cron schedule that is later than `after`.

    Celery computes the next run in the clock of the schedule. This function first converts
    `after` into the zone of the schedule, then adds the remaining time.

    Args:
        cron: A Celery crontab made by `parse_cron`. It must carry its own `nowfun`.
        after: The reference time. It must be timezone-aware.

    Returns:
        An aware datetime in the zone of the schedule.

    Raises:
        ValueError: If `after` is naive.
    """
```

## Writing rules

1. Describe what the code does **now**: read the function, its callees, callers, and tests first.
2. Verify every fact: units, time zones (IST = `Asia/Kolkata`), defaults, limits, failure behavior,
   what is saved.
3. Summary: one imperative sentence, at most 80 chars, ends with a period.
4. Short sentences (about 20 words), active voice, present tense, one word per concept
   ("feed", "article", "prediction", "report", "task run", "setting").
5. No idioms, marketing, "simply", or "just". Do not repeat annotated types in `Args:`.
6. Never include secrets; use placeholders like `<token>`.
7. Put code in backticks; avoid raw `<`, `>`, `{`, `}` outside backticks (MDX output).
8. Lines at most 100 chars.
9. If you find a bug, keep the docstring true to current behavior and report it.

Per kind: views (methods, form data, who may call, response); models/services (invariants,
transactions, exceptions); Celery tasks (args, result shape, providers, time limit, idempotency,
user-startable or not); HTTP clients/parsers (provider, timeout, bad data/status handling);
settings and security code (precedence, limits, secrets, DB-failure behavior).

## Check

```bash
cd docs && npm run reference:check
uv run ruff check .
python docs/scripts/generate_reference.py --no-write --list --source apps/<app>   # backlog
```

## Baseline ratchet

`docs/scripts/docstring_baseline.txt` lists legacy gaps (`path::qualified.name`). It may only
shrink: a fixed gap that is still listed **fails**, so delete its line. Never add lines. To
regenerate after a large change, run
`python docs/scripts/generate_reference.py --no-write --write-baseline` and confirm the diff only
removes lines.
