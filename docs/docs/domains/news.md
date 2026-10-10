---
title: News collection and sentiment
---

# News collection and sentiment

The news domain ingests source items and article text, stores retrieval outcomes, and provides material for company association and sentiment analysis.

## Sources and fetch outcomes

News feeds are managed as database records. A feed carries its source, display name, URL, enabled flag, last-fetch timestamp, last new-item count, and last error state. The migration seeds the default feeds; after the seed, the Ops feed page is the operational source of truth.

A feed collector should:

1. Read enabled records from the database rather than a duplicated hard-coded list.
2. Apply a request timeout and validate the provider response.
3. Parse stable article identifiers and timestamps conservatively.
4. Avoid inserting duplicate feed items.
5. Record a safe result for each feed, including zero new items.
6. Keep credentials and sensitive request details out of logs.

RSS feeds and scraped pages can be incomplete, stale, malformed, redirected, rate-limited, or unavailable. Preserve enough error information for staff to diagnose the source without returning stack traces to ordinary users.

## Article extraction

Where a feed does not contain the full article text, the application can retrieve and extract it. Treat remote HTML as untrusted data. Do not execute page scripts or trust remote markup as safe application HTML. Set timeouts and bound the amount of downloaded or processed data.

## Sentiment pipeline

Sentiment scoring uses the configured local Ollama model. Model address, model name, request timeouts, and analysis options are runtime settings. A scoring result should be traceable to the input article and model/configuration used for it. An unavailable model must be reported as a failure or a pending state, not as neutral sentiment.

## Change checklist

When changing news ingestion or sentiment:

- Test duplicate feed items and repeated fetches.
- Test empty feeds, missing fields, invalid dates, encoding problems, redirects, and HTTP errors.
- Test model timeouts, malformed model output, and empty article text.
- Preserve the per-feed last result shown on Ops > Feeds.
- Update the function docstrings for parsing, normalization, scoring, retry, and error semantics.
- Confirm that normal users see a neutral error message while staff can find the diagnostic in Ops.
