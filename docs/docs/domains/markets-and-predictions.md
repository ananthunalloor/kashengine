---
title: Markets and predictions
sidebar_label: Markets
description: Instruments, quotes, the Nifty 50 prediction rule, its confidence, and how it is evaluated.
---

# Markets and predictions

Code: `apps/markets/`. Tasks: `markets.fetch_quotes`, `markets.predict`.

:::caution
The prediction is a simple rule. It is not a trading signal. Confidence is not a probability.
Do not trust the prediction before the accuracy page shows that it beats the baseline over many
days.
:::

## Instruments

An `Instrument` is a symbol that the code downloads (a Yahoo Finance symbol). Its `kind` is:

| Kind | Use |
| --- | --- |
| `target` | The index that the prediction is for (the Nifty 50). Exactly one exists. |
| `index` | An index that the code only shows. |
| `cue` | A global input to the prediction: US, Asia, oil, the rupee, the India VIX. |

A cue has a `weight` (-1 to 1; a minus sign means that a rise is bad news) and a `scale` (the
move in percent that counts as a full signal; it must be above zero). A superuser edits the
instruments on **Ops > Instruments**. The target cannot be duplicated, disabled, deleted or
changed to another kind.

## Quotes

`markets.fetch_quotes` downloads the daily close and the change in percent with the `yfinance`
package and saves them as `IndexQuote` rows (unique for each symbol and day). It saves only
these two numbers.

:::note
`yfinance` is not an official Yahoo tool. It uses public Yahoo endpoints for personal use. Read
the Yahoo terms for your case. It can break when Yahoo changes something. Then the quotes fail
and the log shows why.
:::

## The trading calendar

A weekday is a trading day, and a weekend is closed, unless the **trading calendar** says
otherwise. The calendar is the table `TradingCalendarDay` (`apps/markets/models.py`). Each row
is one date, with a required reason:

| Kind | Meaning | Session hours |
| --- | --- | --- |
| `holiday` | The market is closed on a weekday. | Not allowed. |
| `special` | The market is open, for example on a Saturday. | Required: a start and a later end, in IST. |

An unlisted weekday opens at 09:15 IST and closes at `MARKET_CLOSE_TIME`. An unlisted weekend is
closed. `trading.is_trading_day`, `session_open` and `session_close` read the table. The
prediction, the evaluation, the daily report, the delivery task and the Ops health checks all use
these functions.

:::caution
The code has **no official holiday feed** and no pre-filled dates. Staff with the Django admin
permission enter each exchange holiday at `/admin/markets/tradingcalendarday/`. Check each date
with the official NSE circular. An empty year shows a warning in the app. If a holiday is not
entered, the code treats it as a trading day, and its prediction ends as void (see below).
:::

The signed-in app shows the status and a year list in the **Trading calendar** window. It reads
`GET /api/app/calendar?year=YYYY`. The status describes the schedule. It does not show the
health of the exchange.

## Upstox data

Upstox is **off** until a superuser turns on `UPSTOX_ENABLED` and saves `UPSTOX_ACCESS_TOKEN` on
**Ops > Settings**. The token is a secret. It goes in the `Authorization` header only, never in a
URL, a log line or an error text. The code does not renew the token. An expired token gives a clear
error. Read the Upstox terms for the storage and the display of data before you turn it on.

Two beat entries start with the first migration. They do nothing while Upstox is off:

| Task | Default time (IST) | What it does |
| --- | --- | --- |
| `markets.upstox_quotes` | Every 5 minutes | Saves a snapshot quote of each mapped company. It runs only in a trading session of the calendar. |
| `markets.upstox_refresh` | Minute 10 of every sixth hour | Saves the history, the due fundamentals, the news and the IPOs. It then starts the scoring and saves the company outlooks. |

A part that fails records a safe error for the company (`upstox_errors`). The old good data stays,
and the page shows the error.

For faster prices, run **one** optional stream worker: `python manage.py stream_upstox` (add
`--symbols` for a subset of at most 100 companies). It is not part of the Compose services. Run
it under your own process supervisor. The worker:

- asks Upstox for a new feed address at each connect, and accepts only a `wss://` address on a
  host that ends with `.upstox.com`;
- checks the certificate;
- saves at most one quote for each company in 5 seconds, with the exchange time;
- stops with an error after 5 failed tries, or at once on invalid data, and never saves a guessed
  price.

The page `/markets/live` lists the saved quotes of the companies. It reads the database only.

## The prediction rule

`markets.predict` runs on trading days (see [the trading calendar](#the-trading-calendar)). It makes a `Prediction` for the day,
unique by `target_date`.

1. **News score.** The average sentiment of the scored news since the last market close. Each
   article counts as much as its relevance. An article with a relevance under 0.2 is not used.
   If there are fewer than `PREDICTION_MIN_ARTICLES` articles, the news counts less.
2. **Global score.** The change of each cue at its last session, cut to -1 to 1 with its
   `scale`, and multiplied by its `weight`. A quote that is older than 4 days is not used.
3. **Score.** The weighted average of the two. `PREDICTION_NEWS_WEIGHT` (0.5) is the weight of
   the news.
4. **Direction.** A score of `PREDICTION_THRESHOLD` or more is `up`. A score of
   `-PREDICTION_THRESHOLD` or less is `down`. Else it is `flat`.

**Confidence** is a number from 0 to 1. It grows when the score is far from the threshold, when
the news score and the global score agree, and when the code has more data. It is not fitted to
data. The strength label comes from the confidence: under 0.4 is `weak`, under 0.6 is
`moderate`, and 0.6 or more is `strong`.

The prediction saves its inputs, so you can see the numbers behind a result. The `notes` list
says what lowered the trust, for example a missing cue.

Settings: the group **Markets and prediction** in [Settings](../reference/generated/system/settings.md).

## Evaluation

The real result of a day is the change of the Nifty 50 close. A change inside
`MARKET_FLAT_BAND_PCT` (0.25 percent) is `flat`.

- The code checks a prediction only when the quote of its day is **final**. A quote is final when
  the code saved it after the close (15:30) plus `MARKET_FINAL_BUFFER_MINUTES`. A row from the
  middle of the session can hold a price that is not the close.
- A prediction is **void** when the market had no session on that day: there is no quote for the
  day, but there are quotes for later days. A void prediction is not counted. With a complete
  trading calendar this does not happen for a holiday, because no prediction is made.
- The accuracy page compares the accuracy with the **baseline**: always guessing the most common
  real direction. At least 30 results are needed before the page says that the numbers are
  enough. A prediction with a confidence of 0.6 or more counts as high confidence. The last 30
  results are the recent window.
- `python manage.py prediction_stats` prints the same numbers.

## Change checklist

- Write down the scale and the sign of each score, and each limit.
- Test fixed inputs and outputs when you change a weight or a limit.
- Test a correct, a wrong, a flat, a missing-quote and a not-yet-evaluable case.
- A prediction for a day must not use data that the code did not have at that time.
