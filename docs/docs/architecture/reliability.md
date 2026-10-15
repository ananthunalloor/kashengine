---
title: Reliability and failure handling
sidebar_label: Reliability
description: How Kash Engine handles retries, time, errors and data quality.
---

# Reliability and failure handling

## Repeated and parallel runs

A scheduled task can run twice (a retry, a restart, or a manual start). Each task is safe to run
again:

- Articles are unique by URL. Reports are unique by date. Predictions are unique by target date.
- `companies.link_news` and the IPO scoring can run again without a change in the result.
- A manual start is refused while a run of the same job is waiting or running. After 30 minutes
  the run no longer blocks, so a lost run cannot lock the job.
- `ops.prune` marks runs that stay `pending` for more than 2 hours, or `started` for more than
  3 hours, as failed.
- A job message that no worker takes within one hour is dropped.

## Time

- The project time zone is `Asia/Kolkata` (IST). The schedule, the market days and the report
  dates use IST.
- Celery computes the next run in the clock of the schedule. With `USE_TZ` on, that clock is UTC.
  The function `apps.ops.schedule.next_after` converts the time first. Do not call the Celery
  method directly.
- The API gives date-time values in UTC with `Z`.
- The code has no list of market holidays. A holiday counts as a trading day. A prediction for
  a holiday ends as **void** and is not counted in the accuracy.
- Weekends: `markets.predict` and `delivery.send_daily_report` do nothing on Saturday and Sunday.

## Errors and logs

- Catch an exception only where the layer can recover, give a safe error, or save a useful task
  result.
- The log keeps the traceback. Users never see it.
- A secret never goes in a log. The Telegram bot token is in the URL of each Telegram request, so
  every error text goes through `redact()`, and the `httpx` logger stays at `WARNING`. The log
  viewer hides secrets again when it shows a line.
- Do not return a success-shaped value when a collection or a prediction failed.

## Data quality

- A value that is not known is `null`, not `0`. A neutral sentiment is a real score near zero. An
  article that is not scored has `sentiment: "unscored"`.
- Freshness limits are settings. For example `NEWS_STALE_AFTER_HOURS` (7) and
  `IPO_METRIC_MAX_AGE_HOURS` decide when data is too old to use.
- The health page separates four cases: no data, old data, a provider that failed, and a valid
  empty result.
- Rules that must hold under parallel requests are database constraints (unique keys), not only
  Python checks.
- A prediction is not trusted before the accuracy page shows that it beats the baseline of always
  guessing the most common result. At least 30 results are needed (`MIN_RESULTS_TO_TRUST`).
