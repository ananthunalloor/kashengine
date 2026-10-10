---
title: Company data
---

# Company data

The companies domain stores company records and refreshes available metrics from Screener.in or other configured sources. The scheduled refresh supports the analysis pipeline; it must not make user-facing page requests wait for a provider call.

## Data rules

- Use a stable company identifier or normalized symbol for matching.
- Treat provider fields as optional: a missing value is not automatically zero.
- Keep the raw provider representation separate from normalized domain values when it helps debugging or repeat processing.
- Apply HTTP timeouts and explicit handling for rate limits, redirects, malformed pages, and provider changes.
- Make refresh operations safe to rerun. Avoid overwriting a valid value with a parsing failure.
- Record a safe status so operators can distinguish a stale company record from a current one.

## Testing changes

Test known company pages with representative fixtures rather than scraping a live provider during unit tests. Include missing fields, numeric formatting changes, invalid values, rate limits, and partial records. Mock network boundaries in unit tests and keep any integration test that contacts a real provider opt-in.

The generated Python API reference lists the current functions in `apps/companies/`. Use it with the source and tests before changing a refresh contract.
