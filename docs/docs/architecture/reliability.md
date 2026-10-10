---
title: Reliability and failure handling
---

# Reliability and failure handling

## Idempotency

Scheduled tasks can overlap with retries, restarts, or manual runs. Before adding a task, define its idempotency key or natural uniqueness rule. For destructive or externally visible work, prevent duplicate concurrent runs and add a confirmation step to the Ops registry when appropriate.

## Time and scheduling

- Use the configured project time zone (`Asia/Kolkata`) for market schedules and operator-facing times.
- Store schedule definitions in `django-celery-beat`; do not add a second hard-coded `CELERY_BEAT_SCHEDULE` source.
- Be explicit about aware datetimes. Convert times to the schedule zone before calculating next-run timestamps.
- Test boundary times around midnight, market close, disabled tasks, and daylight/time-zone conversions where applicable.

## Errors and logs

- Catch an exception only when the current layer can recover, translate it to a safe error, or record a useful task outcome.
- Preserve the traceback in restricted server logs where useful; do not expose it to ordinary users.
- Never log secrets, tokens, database URLs, authorization headers, or a full Telegram URL.
- Avoid broad exception handling that turns a failed collection or prediction into a success-shaped return value.

## Data correctness

- Make freshness thresholds explicit and configurable when operators need to tune them.
- Distinguish “no data,” “stale data,” “provider failed,” and “valid empty result.”
- Use database constraints to enforce invariants that must hold under concurrent requests.
- Add regression tests when a bug changes scheduling, scoring, source parsing, or secret handling.
