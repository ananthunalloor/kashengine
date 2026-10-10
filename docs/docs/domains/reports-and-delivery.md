---
title: Reports and Telegram delivery
---

# Reports and Telegram delivery

The reports domain assembles a daily report from persisted news, sentiment, company, IPO, and market data. The delivery domain sends the report to configured Telegram destinations. Report composition and external delivery should remain separate so the content can be tested without network access.

## Report composition

Document which date the report represents, how articles are selected and ordered, how summaries and scores are displayed, and what happens when a data source is missing or stale. Keep formatting deterministic where possible. Limit the report size using the configured setting rather than a second hard-coded limit.

## Telegram safety

- Read the API URL, bot token, and destination IDs from the central settings layer.
- Never log the full Telegram URL; Telegram URLs contain the bot token.
- Keep the `httpx` logger at WARNING unless a reviewed redaction mechanism makes higher levels safe.
- Use request timeouts and handle rate limits and provider errors explicitly.
- Record delivery outcome without storing the token or secret-bearing URL in a task result, audit event, or user-visible error.
- Keep manual delivery actions restricted and require confirmation when the operation sends an external message.

## Testing

Test report composition as a pure or isolated operation using persisted fixtures. Mock HTTP requests in delivery tests. Verify success, timeout, HTTP failure, malformed response, missing destination, and secret redaction. Do not use a live Telegram token in automated tests.
