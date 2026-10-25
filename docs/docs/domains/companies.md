---
title: Companies
sidebar_label: Companies
description: Company records, name matching in news, Upstox data, the company outlook, and the Screener.in refresh.
---

# Companies

Code: `apps/companies/`. Tasks: `companies.link_news`, `companies.refresh_stale`.

## Records

A `Company` has a symbol, a name, a sector, a list of aliases, the data from Screener.in and an optional
Upstox instrument key.
You can add companies with the command `import_companies` (a CSV file with the columns symbol,
name, sector and aliases, or the built-in starter list with `--starter`).

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

A company gets Upstox data only after an administrator enters its exact **instrument key** in Django
admin (for example `NSE_EQ|INE002A01018`). The key must match the pattern of an NSE or BSE
equity key. The code never guesses a key from a symbol. One key can belong to one company.

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
