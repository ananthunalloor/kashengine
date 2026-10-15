---
title: Companies
sidebar_label: Companies
description: Company records, name matching in news, and the Screener.in refresh.
---

# Companies

Code: `apps/companies/`. Tasks: `companies.link_news`, `companies.refresh_stale`.

## Records

A `Company` has a symbol, a name, a sector, a list of aliases and the data from Screener.in.
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
