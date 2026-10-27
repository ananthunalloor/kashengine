---
title: Companies
sidebar_label: Companies
description: Company records, name matching in news, Upstox data, the company outlook, and the Screener.in refresh.
---

# Companies

Code: `apps/companies/`. Tasks: `companies.link_news`, `companies.refresh_stale`.

## Records

A `Company` has a name, a primary symbol, a sector, a list of aliases, an ISIN and an optional
primary Upstox instrument key. The exchange instrument refresh groups NSE/BSE equity listings by
ISIN, so one company record can show multiple exchange-specific symbols. It prefers the NSE symbol
as the primary display value when both listings exist. Each Upstox key stays attached to its exact
exchange instrument; a catalog refresh does not enable quote ingestion for every listed company.
You can add companies with the command `import_companies` (a CSV file with the columns symbol,
name, sector and aliases, or the built-in starter list with `--starter`).
Run `python manage.py refresh_instruments` to import the active NSE/BSE listings and link them to
companies by ISIN. NSE main-board and SME share series and BSE share series are included; funds,
bonds and other non-share cash instruments remain in the full instrument catalog without being
presented as companies. The refresh also updates the separate instrument catalog and runs daily
at 06:20 IST.

The directory can also filter the official Nifty 50, Next 50, 100, 200, 500, Midcap 50/100/150,
and Smallcap 50/100/250 constituent groups. Run `python manage.py refresh_index_constituents` once
after deployment and to update them manually; the task runs daily at 06:30 IST. The importer
validates every CSV before replacing any saved memberships and matches constituents to companies
by ISIN.

## Match companies in news

`CompanyMatcher` finds the companies that a text names. The rules are simple on purpose, so that
false matches stay rare:

- The matcher searches the **title and the summary**. It does not search the full text, because
  a long article names other companies only in passing.
- A name or an alias must match as **whole words**, in any letter case.
- The matcher removes words like "Ltd", "Limited", "Inc" and "Pvt" from a name before it
  compares.
- It keeps `&`, so "L&T" is one word.
- A term must have at least 3 characters.

`link_articles` saves the links and is safe to run again. `companies.link_news` runs for recent
articles. The command `link_news --all` checks all articles.

## Upstox company data

[Upstox](../domains/markets-and-predictions.md#upstox-data) can fill saved tables for a company:

| Table | Holds |
| --- | --- |
| `CompanyQuote` | A price with the time of the exchange. The `mode` is `snapshot` or `stream`. |
| `CompanyCandle` | One daily open, high, low, close and volume. It is unique for each company and day. |
| `CompanyFundamentals` | A full copy of the profile, the key ratios and the statements. Old copies stay. |
| `CompanyOutlook` | The experimental outlook for the next session, with its inputs. |

A company gets Upstox fundamentals, quotes and candles only for its primary exact **instrument
key** (for example `NSE_EQ|INE002A01018`). The directory also shows its other NSE/BSE equity
listings, but those listings do not imply that a quote or fundamentals are saved for each exchange.
The code never guesses a provider key from a symbol.

The pages read these tables only. No page calls Upstox.

## The company outlook

`save_outlook` (`apps/companies/outlook.py`) makes a simple outlook for the next trading day:

- **Momentum** is the change of the close over the last 20 sessions, in percent, divided by 10 and
  cut to -1 to 1.
- **News** is the average sentiment of the scored news of the last 7 days that names the company,
  weighted by relevance. If there is no scored news, the score is the momentum alone.
- **Score** is `0.7 * momentum + 0.3 * news`. A score above 0.15 is `up`, below -0.15 is `down`,
  else `flat`.

The code makes **no outlook** without 21 completed daily candles that end on the latest completed
day. It saves the inputs with each outlook, so you can check them. If the target day and the
inputs are the same as the last outlook, the code keeps the last one.

:::caution
The outlook is a simple rule. It is not a trading signal, a probability or a price target.
:::

## The company page

The React page `/companies/<id>` shows the summary, the saved fundamentals, the price history, the
linked news and IPOs, and the evidence of the outlook. The API is `GET /api/app/companies/{pk}`. A
part of the page needs a feature: prices and the outlook need `markets`, news needs `news`, IPOs
need `ipos`. A user without the feature does not get that part.

## Stocks to watch today

The Today dashboard includes a news-only company watchlist when the account has **Companies,
Markets and News** access. Access is checked before the watchlist reader runs. Reading never
calls providers, scores news with an LLM, writes predictions or changes company records.

The watchlist examines at most the latest 300 scored, timestamped, company-linked articles from
the past 36 hours. Publication and scoring times must not be in the future. Sentiment must be in
[-1, 1] and market relevance in [0.5, 1]. Truncated coverage is explicit. Up to eight companies
are ranked by average absolute sentiment times relevance, with latest news time as a tie-breaker;
this is news attention, not expected return or confidence.

Each company shows a relevance-weighted sentiment balance. Above +0.15 gives a bullish news
bias, below -0.15 gives bearish, otherwise neutral. If positive and negative individual stories
both cross those thresholds, the view is mixed regardless of the average. Cards show article
and source counts, latest publication time, and up to three news links with saved sentiment
explanations. Mixed views include both positive and negative evidence even when one side is
weaker. One-article evidence is labeled. Repeated outlets are not independent
evidence, and article sentiment may not describe the impact on every linked company.

The trading calendar respects holidays and special sessions. Closed days and completed sessions
show the next session instead of today's movement calls. The snapshot is dated and not live;
reload to obtain a fresh snapshot. It is **not an archived or backtested forecast**. No accuracy,
probability, expected price return or price target is inferred from sentiment alone.

## Company detail tools

Fundamentals use a searchable, sortable, paginated table with category and assessment filters.
Company and sector values are shown side by side. Profitability and leverage assessments are
relative to the supplied sector benchmark, not an overall good/bad verdict on the stock.
Missing or invalid numbers are not treated as zero; unsupported comparisons are marked as
needing context. The page shows the saved timestamp rather than a provider badge.

The **Is this company overvalued?** section compares positive saved P/E, P/B and EV/EBITDA
company/sector pairs. Each shows `(company / sector - 1) * 100` as a premium or discount.
All comparable ratios above the sector (allowing equal ones) give a sector-premium verdict;
all below give a discount; opposing comparisons are mixed and equal ratios are in line.
No comparable pairs gives insufficient data. Identical duplicates count once; conflicting
values, unexpected percentage units and non-positive multiples are excluded. A one-ratio
verdict is explicitly marked as limited evidence. The save time is shown, not implied live.
This is relative pricing, not proof of over/undervaluation or an absolute fair-value target;
growth, risks, accounting basis, reporting periods and sector composition still need review.

The daily candle chart is 440px tall, with session ranges (20 sessions per month), zoom,
horizontal drag/button panning, a snapped crosshair and OHLCV readout on hover/touch or keyboard
inspection. Volume, SMA 20, SMA 50 and the illustrative projection can be toggled. Moving
averages use all available prior history, not just the visible window. Fullscreen and reset
controls are available. Arrow keys inspect candles; Shift+arrows pan; +/- zoom.

### Prediction verification and deviations

The page separates **historical chart simulations** from **saved engine outlook results**.
The current dashed projection is unverified future data, not evidence of accuracy.
The default view leads with a baseline verdict, direction-match rate, average price miss and
the latest direction miss (or latest comparison if none missed), with up to two related news
items. Saved outlooks have a separate summary of matched, pending and unverifiable results.
Full result tables and methodology are collapsed by default to keep the overview readable.

- At each historical cutoff, the simulation fits only the preceding 20 closes and extrapolates
  exactly the same slope used by the chart. Horizons are 1, 5 or 20 saved sessions; only completed
  targets are scored. The latest 60 eligible comparisons show projected/actual close, signed
  deviation, MAE, RMSE, MAPE, mean deviation and direction match rate. A no-change-price MAE on
  the same samples is the baseline. Overlapping windows are not independent; missing saved
  sessions can stretch the horizon. This reconstruction is not an archived/live track record.
- The API supplies up to 120 recent instrument-scoped saved outlooks, only with both Markets and
  News access. The earliest saved record per target in that bounded history is evaluated.
  Outlooks without baseline evidence, saved before their baseline completed, or saved at/after
  target-session open (09:15 IST) are not verifiable. Pending targets are not scored, and a
  missing target close is never replaced with another day's price.
- Direction checks use an explicit **+/-0.5% realized-return flat band**. This is an evaluation
  convention, not the outlook model's score threshold. A direction-only outlook has no price
  target, so the page never calculates a fabricated price error from its score.
- Deviation rows explain observed reversal/magnitude differences and saved momentum/news
  contributions. Available timestamped company-linked news is linked only if published after
  cutoff/issuance and by target-session close. Context is limited to the latest 30 saved articles;
  missing/undated news does not establish that no event occurred. Sentiment and temporal overlap
  do **not** prove causation. Without market benchmarks, corporate actions and event evidence,
  the specific cause remains unknown. Revised historical data can affect these evaluations.

The trade setup watchlist uses at least 21 valid daily candles. It reports the prior 20-session
high/low, SMA 20, momentum and volume confirmation; positional trend alignment needs SMA 50.
Swing scenarios require a completed close above resistance with above-average volume.
An illustrative stop at support and 2R level describe arithmetic risk, not an execution signal
or predicted target. History older than seven calendar days forces a wait state. Unsupported
intraday/short-selling setups and missing data are explicitly marked as not assessable.
These educational rules are not personalized advice and have not been backtested.

## Screener.in data

:::warning
The Screener.in code is **off** until `SCREENER_ENABLED` is true. The terms of Screener.in allow
only personal, non-commercial viewing. They forbid copying and public display. Read the terms and
decide if your use is allowed before you turn it on.
:::

When it is on, `companies.refresh_stale` reads each company page that has no data or that is older
than `SCREENER_REFRESH_DAYS` (7). A company that was never fetched goes first.

- The code tries the consolidated page first.
- It waits `SCREENER_DELAY_SECONDS` (5) between requests.
- One run takes at most `SCREENER_BATCH_SIZE` (100) companies.
- After 5 errors in a row the run stops.
- A page that has a layout that the parser does not know raises `ScreenerParseError`. The old data
  stays. A bad page does not overwrite good data.
- A missing value is `null`, not zero. A table keeps at most 8 columns.

No web page waits for Screener.in. The pages read the saved data.

## Test

Use saved pages as fixtures. Do not call the live site in a unit test. Test a missing field, a
changed number format, a bad value and a rate limit.
