---
title: Reports and delivery
sidebar_label: Reports and delivery
description: How the daily report is built from stored data, and how it is sent by email or Telegram.
---

# Reports and delivery

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

### How scores are shown

The database keeps news scores, IPO scores and prediction scores from -1 to 1. It keeps the
confidence (shown as "strength") from 0 to 1. The Telegram report, the React app and the archived
pages show them on a scale of 1 to 10. The formula is `1 + 9 * value`. A signed score first
becomes `(score + 1) / 2`, so 0 is shown as 5.5/10. The function is `score_out_of_ten` in
`apps/reports/formatting.py`. The HTTP API returns the stored values, not the 1 to 10 text.

## Delivery

`delivery.send_daily_report` runs on weekdays at 07:30 and 07:50 IST. On a day when the market is
closed (a weekend or a saved holiday) it does nothing. It builds today's report (or reuses it),
sends Telegram deliveries, then emails reports to accounts that have verified their email and
opted in.

`deliver_report` sends the text to each configured Telegram chat and each linked user chat whose
owner selected Telegram delivery:

- A chat that already got this report (a `sent` row in `DeliveryLog`) is skipped. So the retry run
  at 07:50 sends only to the chats that failed. A manual send with `force` sends to all chats again.
- One chat that fails does not stop the others. Each try writes a `DeliveryLog` row with the
  status, the recipient and a redacted error (at most 500 characters).
- If the token or the chat list is empty, the function raises `DeliveryNotConfiguredError`. The
  task records the Telegram failure separately; email delivery still runs.
- Email delivery requires both a verified email and explicit opt-in. Each send is logged, and
  retries skip an email address that already received that report.

## Account sign-up and destinations

New accounts are invite-code gated by default. Configure SMTP settings before allowing sign-up.
Open **Ops > Access > Invite codes** to inspect the invitation table: reference, state
(Available, Used, or Revoked), creator, creation time, redemption time, redeemed account, and
email address. The table supports search, state filtering, sorting, and pagination.
Staff can inspect it; only superusers can **Generate invite code** or **Revoke** an unused code.
Generation and revocation are recorded in the audit trail without including the code.
Alternatively, in Django admin, open **Delivery > Signup invites > Add**, then save.
Copy the code from the success message immediately: it is shown only once, and only its
SHA-256 digest is stored. Share it privately with one person. Each invitation registers exactly
one account; it is consumed when registration succeeds, even before email verification. Invalid
forms do not consume it. Email-send failures do not undo account creation: users can log in and
request a fresh verification email later. Administrators can revoke unused invitations.
The old shared `SIGNUP_INVITE_CODE` environment variable is no longer supported.

The sign-up form and account-created confirmation use the public React layout, while Django
handles the CSRF-protected form submission and validation. Accounts can log in immediately, but
all regular users (including existing accounts) must verify their email before using any product
feature, API, API token creation, or linked Telegram reports. Staff and superusers are exempt.
Account, verification/resending, logout, and token revocation remain available while locked.
The navigation shows only Account until verification, and direct feature URLs redirect there.
Existing accounts without an email address must contact an administrator to add one.
To verify email ownership manually, a superuser can open **Django admin > Authentication and
Authorization > Users**, select the account(s), choose **Mark email verified (only after confirming
email ownership)**, and click **Go**. Independently confirm ownership first. The action requires
a valid email address, records each change in the Ops audit trail and Django admin history, and
removes pending verification links. It does not reactivate disabled accounts, enable reports, or
change subscriptions. Already-verified accounts are left unchanged. The Users table includes an
**Email verified** indicator; users should reload after manual verification.
Verification links expire after `EMAIL_VERIFICATION_HOURS`. Account settings provides a
**Send verification email** button for requesting a new link, with a one-minute cooldown.
A successfully sent replacement invalidates the previous link; a failed resend preserves it.
Verification never reactivates an account disabled by an administrator.
To make registration open later, set
`SIGNUP_INVITE_REQUIRED=false`.

Sign-up also requires an unchecked-by-default agreement checkbox linking to `/legal/`.
The accepted agreement version and timestamp are recorded under **Delivery > Legal acceptances**.
This requirement also applies to open registration. The page contains starter Terms of Use and
a Privacy Notice, including financial-information disclaimers. Have qualified counsel review and
adapt these for your operator, jurisdiction, contact details, provider arrangements, and retention
requirements before launch. Publish a real operator support/contact channel. When changing the
agreement, preserve the previous text in version control and update `LEGAL_VERSION` in
`apps/web/signup.py` plus the effective date and text in `apps/web/templates/web/legal.html`.
Existing users are not automatically prompted to accept a new agreement.

On the Account page, users can select email, Telegram, or both. Telegram is linked by opening a
short-lived bot deep link and sending its `/start` payload. Configure `TELEGRAM_BOT_USERNAME` and
`TELEGRAM_WEBHOOK_SECRET`, then register
`https://<SITE_ADDRESS>/api/telegram/webhook/` with Telegram as the bot webhook URL and the same
secret token. Do not use `getUpdates` while the webhook is configured. Linked chat IDs are never
returned by the account API.

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
