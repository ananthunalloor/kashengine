---
title: Reports and Telegram delivery
sidebar_label: Reports and delivery
description: How the daily report is built from stored data, and how it is sent on Telegram.
---

# Reports and Telegram delivery

Code: `apps/reports/`, `apps/delivery/`. Task: `delivery.send_daily_report`.

## The report

`build_report(date)` makes the report of one date from the data in the database. A `Report` is
unique by date. The report has four parts:

1. The Nifty 50 outlook: the direction, the strength label, the score, and the last result.
2. The news: the best and the worst stories (`REPORT_NEWS_ITEMS`, 3 each), with a relevance of at
   least `REPORT_NEWS_MIN_RELEVANCE` (0.4) and a score of at least 0.2 in either direction.
3. The IPOs: the lists of IPOs to look at (`REPORT_IPO_ITEMS`, 6 for each list, within
   `REPORT_IPO_DAYS_AHEAD`, 7 days).
4. A short warning that the report is not advice.

The builder **only reads the database**. It does not call the LLM and does not use the network.
So it works when the LLM server or Yahoo is down. It says what is missing. The strength label
comes from the confidence: under 0.4 is weak, under 0.6 is moderate, else strong. The text says
that the strength is not a probability.

`Report.text` is plain text. There is no markup, so Telegram cannot refuse the message because of
bad markup. `Report.data` keeps the numbers and the lists for the web page and the API.

## Delivery

`delivery.send_daily_report` runs on weekdays at 07:30 and 07:50 IST. On a Saturday or a Sunday it
does nothing. It builds today's report (or reuses it), then calls `deliver_report`.

`deliver_report` sends the text to each chat in `TELEGRAM_CHAT_IDS`:

- A chat that already got this report (a `sent` row in `DeliveryLog`) is skipped. So the retry run
  at 07:50 sends only to the chats that failed. A manual send with `force` sends to all chats again.
- One chat that fails does not stop the others. Each try writes a `DeliveryLog` row with the
  status, the recipient and a redacted error (at most 500 characters).
- If the token or the chat list is empty, the function raises `DeliveryNotConfiguredError`. The
  task logs a warning and returns `not_sent`. The report is still saved.

The Telegram client sends plain text (no parse mode). A message can have 4096 characters at most.
A longer text is split at blank lines at 4000 characters. On HTTP 429 the client waits once if
`retry_after` is 30 seconds or less.

:::warning
If a later part of a split message fails, a retry sends all parts again, so the first part can
arrive twice. The report is made to be shorter than one message, so this is rare.
:::

## Telegram safety

- The bot token is a secret. It is encrypted in the database and shown never. See
  [Runtime settings](../operations/runtime-configuration.md).
- The URL of each request holds the token. Every error text goes through `redact()`. The
  `httpx` logger stays at `WARNING`, so no URL is logged.
- The delivery log, the audit trail and the task result never hold the token.
- The jobs **Check the Telegram bot** and **Send a Telegram test message** on **Ops > Jobs** help to find
  the chat ids and test the setup. The delivery pages show the log. The API masks the recipient to
  its last four characters and shows the error text to staff only.

## Test

Test the report as a read-only operation on saved rows. Replace the HTTP client in the tests of
delivery. Test success, timeout, an HTTP error, a bad answer, a missing chat and the redaction.
Never use a real token in a test.
