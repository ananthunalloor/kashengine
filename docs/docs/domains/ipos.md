---
title: IPOs
sidebar_label: IPOs
description: IPO records, data sources, the score formula, verdicts, and listing results.
---

# IPOs

Code: `apps/ipos/`. Tasks: `ipos.collect`, `ipos.refresh_metrics`, `ipos.score`.

:::caution
The IPO score is a simple rule on rumour data. The grey market premium (GMP) is unofficial. The
score is not advice.
:::

## Data

An `Ipo` has a name, a category (`mainboard` or `sme`), a status (`upcoming`, `open`, `closed`
or `listed`), dates, the price band, the lot size, the issue size (crore rupees), the GMP, the
subscription (in times), the listing price and gain, the score, the verdict and the inputs of the
score (`score_inputs`).

You can add IPOs by hand with `import_ipo_csv` (columns: name, open_date, close_date,
listing_date, price_band_low, price_band_high, lot_size, issue_size_cr, category, gmp,
subscription_times and more) and `update_ipo`. A value that you set by hand is not overwritten by
an older value from a source.

## Sources

All three fetches are **off by default**. They read websites that say "all rights reserved", and
the project has no written permission for automated use. Read the terms of each site and use the
data for yourself only. The code obeys `robots.txt` and reads only a few URLs a day.

| Setting | Source | What it gives |
| --- | --- | --- |
| `IPO_FETCH_ENABLED` | The IPO list (`IPO_SOURCE_URLS`, chittorgarh.com by default). The code reads the JSON feed that the page uses. This feed is not a public API and can change at any time. | Names, dates, price band, lot size, issue size. No GMP, no subscription. |
| `IPO_GMP_ENABLED` | A live GMP table (`IPO_GMP_URL`, investorgain.com by default). | The GMP and the subscription of open IPOs, with the time that the source gives. |
| `IPO_LISTING_ENABLED` (on) | Yahoo Finance through `yfinance`. | The listing price: the open price of the first trading day. The code tries `SYMBOL.NS`, then `CODE.BO`. |

A fourth source is **Upstox** (`UPSTOX_ENABLED`, see [Upstox data](./markets-and-predictions.md#upstox-data)).
`markets.upstox_refresh` reads the IPO lists of all four stages (upcoming, open, closed, listed)
and the detail page of each IPO. It uses the same save rules as the other sources. The detail data
(`upstox_data`), the Upstox id and the time of the update are saved on the IPO. An IPO whose ISIN
matches a saved company links to that company. An IPO with invalid details is skipped and logged.

:::note
The source code was tested on saved sample data only, not against the live services. If a source
changes its layout, the fetch fails and the log shows why. The old data stays.
:::

New IPOs that opened more than `IPO_KEEP_DAYS` (60) days ago are skipped. The code checks for a
listing result for `IPO_LISTING_CHECK_DAYS` (14) days.

## The score

`ipos.score` scores the IPOs that did not list yet. The rule has three signals. Each one goes from
-1 (bad) to 1 (good):

| Signal | Weight | Rule |
| --- | --- | --- |
| GMP | 0.45 | The GMP as a percent of the upper price band. 30 percent or more is the full signal. The code uses it only when it is fresh (`IPO_METRIC_MAX_AGE_HOURS`, 72 hours since the **time of the source**). |
| Subscription | 0.40 | The number of times the issue was bought, on a log scale. 1 time is 0. 50 times or more is 1. Less than 1 time is negative. The code uses it only when it is final (after the close), because early numbers are always low. |
| News | 0.15 | The average sentiment of the news of the last `IPO_NEWS_DAYS` (14) days that names the IPO. With fewer than 3 articles it counts less. |

The score is the weighted average of the signals that exist. A signal that is missing is left
out. It does not count as zero. The app and the report show the score on a scale of 1 to 10 (see
[How scores are shown](./reports-and-delivery.md#how-scores-are-shown)). The stored value stays
between -1 and 1.

The **verdict**:

| Verdict | Rule |
| --- | --- |
| `good` | The score is `IPO_GOOD_SCORE` (0.3) or more. |
| `weak` | The score is under `IPO_WEAK_SCORE` (0.1). |
| `mixed` | The score is in between. |
| `unknown` | The IPO has no GMP and no subscription. News alone is too thin. |

The inputs of each score are saved in `score_inputs` (the list `signals` and the list `notes`
that says why an input was not used). The API shows them on `GET /api/v1/ipos/{ipo_id}`.

## Results

After the listing, the code saves the listing price and the gain in percent against the upper
price band. A gain of `IPO_GOOD_GAIN_PCT` (10) or more counts as "did well". The command
`ipo_stats` compares the verdicts with the real results. At least 20 results are needed before
the numbers are trusted.

## Change checklist

- For each signal, write the source field, the unit, the formula, the weight and what happens
  when the value is missing or old.
- Test the scale, the sign, the limits, the missing-value case and the order.
- Test with saved provider pages. Never use a live site in a test.
- Keep the disclaimer visible on the pages and in the report.
