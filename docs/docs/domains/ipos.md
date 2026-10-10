---
title: IPO data and scoring
---

# IPO data and scoring

The IPO domain stores IPO records, refreshes data from configured sources, calculates scores, and presents a list of offerings to watch. The web interface should read stored results instead of doing a live scrape for each page request.

## Scoring contract

For every scoring factor, document:

- The source field and its units.
- The normalization formula and range.
- The weight and whether larger values improve or reduce the score.
- The behavior when the source value is missing, invalid, stale, or not applicable.
- The final score range and sort order.

Do not treat missing financial data as a score of zero unless the scoring specification explicitly requires it. Keep the calculation deterministic so it can be tested using fixed fixtures.

## Provider boundary

External IPO pages can change their structure. Use timeouts, validate extracted fields, and save safe refresh outcomes. An individual provider failure should not corrupt a previously valid IPO record. Unit tests should use saved representative provider responses rather than depending on a live website.

## Review checklist

When changing a score or refresh routine, add tests that prove the scale, sign, bounds, missing-value behavior, and ordering. Update function docstrings and this guide whenever any scoring factor or interpretation changes. Keep the site's financial disclaimer visible.
