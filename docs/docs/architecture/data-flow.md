---
title: Data flow
---

# Data flow

This page describes the intended high-level flow. Exact task names, arguments, and model fields are documented by the source modules and the generated [Python API reference](../reference/generated/index.md).

## News-to-report flow

1. Enabled news feeds are read from the database.
2. Scheduled collection tasks fetch and parse feed items. The application stores new items and records the latest outcome for each feed.
3. Where needed, article pages are retrieved and article text is extracted. External HTTP requests must use explicit timeouts and must not log credential-bearing URLs.
4. News is associated with company records where the available data supports that link.
5. Sentiment tasks use the configured local LLM. They store the result and associated metadata so work is not repeated unnecessarily.
6. Market inputs and global cues are read for prediction. Instrument weights and scales are operator-controlled data.
7. Report composition selects the report content and delivery sends it to the configured Telegram destination.
8. The web interface reads stored data; the Ops area exposes job runs, health checks, metrics, and configuration state.

## Task execution and observability

Celery workers execute queued tasks. The database-backed Beat scheduler publishes recurring tasks. Ops records task runs and exposes status, duration, worker, result, and safe error details. A task that has been queued or is running must not be launched again through the manual Ops action until the existing run finishes.

## Failure boundaries

- A provider can fail or return malformed content. Record a safe failure outcome and keep later work eligible to retry according to the task's policy.
- Missing, stale, or incomplete data must be visible to health checks and must not be silently interpreted as a reliable prediction.
- A model server can be unavailable. Separate model-server health from the status of records already stored.
- A Telegram request can fail. Keep the token out of log output and audit details; make delivery status observable without exposing request URLs.
- A database setting may be unavailable during a database error. The settings layer falls back to environment values so configuration access has a defined degraded mode.

When changing a flow, document idempotency, retry behavior, transaction boundaries, data freshness, and how an operator can diagnose failure.
