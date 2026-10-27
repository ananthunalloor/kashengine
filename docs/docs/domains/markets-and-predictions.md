---
title: Markets and predictions
sidebar_label: Markets
description: Instruments, quotes, the Nifty 50 prediction rule, its confidence, and how it is evaluated.
---

# Markets and predictions

Code: `apps/markets/`. Tasks: `markets.fetch_quotes`, `markets.predict`,
`markets.refresh_forecasts`, `markets.train_forecasts`, `markets.watchdog`.

:::caution
The prediction is an experimental rule unless a trained challenger passes chronological
validation. It is not a trading signal. Confidence is not a calibrated probability.
Do not trust the prediction before the accuracy page shows that it beats the baseline over many
days.
:::

## Dynamic forecasts and independent watchdog

Migrations add three editable beat entries without replacing operator-edited schedules:
forecast refresh every 15 minutes, an independent audit seven minutes later, and daily model
training at 05:00 IST. Restart workers and beat after applying migrations and restoring
dependencies with `uv sync`. Provider collection and sentiment scoring remain separate jobs;
company history requires Upstox, valid instrument mappings and sufficient completed candles.

`ForecastSample` records point-in-time features for each entity and target session. Refreshes
can replace a pending snapshot only before its opening deadline. Afterwards it is frozen;
actual outcomes are attached separately. Future-published or not-yet-scored news cannot be
used, same-session closes cannot enter premarket cues, and forced market prediction runs
cannot rewrite an issued forecast after opening.

`ForecastModel` stores a scikit-learn regularized logistic classifier as JSON coefficients and
scaling parameters, never executable pickle data. Each family (market, pooled companies,
IPOs) trains separately. Validation needs 60 earlier training dates and at least 20 later dates,
with all entities on a date kept together. Outcomes unavailable at the first validation
forecast are purged from training. At least two classes with ten training examples each are
required. The model must outperform both the holdout majority-class baseline and the existing
rule by five percentage points. The validated fit itself is deployed, not an unvalidated refit
using holdout labels. Seven-day model expiry and daily revalidation limit stale model use.
Until enough prospective samples exist, the rule is explicitly experimental; this is not a
claim that either rule or model is accurate.

The watchdog is independent deterministic verification, not an LLM review. It recalculates
rules and independently replays classifier outputs using retained model versions, validates
finite normalized inputs and publication deadlines, and compares stored
publications with their recorded decisions and strengths. It withholds invalid predictions,
withdraws cached market-report copies and logs reasons. Withheld market predictions do not
enter accuracy statistics. The browser shows **Withheld**, never a flat/neutral substitute;
API v1 omits withheld history and returns 404 if the newest outlook is withheld.

The first audit withholds active legacy forecasts without verified point-in-time provenance.
It does not fabricate historical training examples; subsequent valid pre-session refreshes
create new evidence.

**Ops > Jobs** exposes refresh, training and audit jobs. Read-only **Forecast models** and
**Forecast samples** in Django admin show metrics, evidence, actual outcomes and audit reasons.
The watchdog cannot prove upstream prices are true or certify future accuracy. The client-side
company chart extrapolation remains illustrative and is not this trained forecast.

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

### NSE/BSE instrument catalog

The `markets.refresh_instruments` task downloads Upstox's public daily BOD JSON master; it does not
need an Upstox API token. It runs daily at 06:20 IST and can also be started with
`python manage.py refresh_instruments`. The import validates the complete file before writing and
deactivates removed contracts only after a successful refresh. It includes Upstox-provided NSE and
BSE cash, index and derivative records, including the NSE currency/commodity and BSE currency
segments present in the source, but excludes other exchanges such as MCX. The company directory
groups equity listings with the same ISIN and shows each exchange symbol.

The app's `/markets/instruments/` page and `/api/app/markets/instruments` endpoint provide search
and filters for exchange, segment and instrument type. The listing is an instrument catalog, not a
quote feed: it does not create historical or live prices for every catalog entry. Coverage follows
the current Upstox instrument master and can differ from the exchanges' complete official security
lists. See the [Upstox instrument master documentation](https://upstox.com/developer/api-documentation/instruments/).

The Companies filters use NSE Indices constituent CSVs for Nifty broad-market, Midcap and Smallcap
indexes. `markets.refresh_index_constituents` validates and saves these lists daily at 06:30 IST;
`python manage.py refresh_index_constituents` runs it manually. On Today, the gainers, losers and
market-breadth cards use the latest saved company quotes with a previous close, restricted to the
most recent quote date. They are not full-market rankings: coverage depends on companies with
Upstox quotes saved in this app.

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

Live prices come from the stream worker `python manage.py stream_upstox`. Compose runs it as
the `streamer` service in dev and prod. Run only **one** for each Upstox token. The worker:

- follows every mapped company and the indices of `UPSTOX_STREAM_INDICES` (default Nifty 50,
  Sensex, Nifty Bank and India VIX) in **full** mode. This mode has the last price, the day OHLC,
  volume, the average price, the total buy and sell quantity and 5 levels of depth. Upstox
  allows 2000 instruments for each connection. `--symbols` limits the companies, and
  `--no-indices` drops the indices;
- asks Upstox for a new feed address at each connect, and accepts only a `wss://` address on a
  host that ends with `.upstox.com`;
- checks the certificate;
- keeps the newest value of each instrument in `LiveSnapshot`, and saves at most one
  `CompanyQuote` for each company in 5 seconds, with the exchange time. These writes send no
  model signal;
- broadcasts the changed quotes and the exchange session state about once a second to the
  `realtime` service, through the Redis channel layer;
- reconnects forever, with a wait that doubles up to 60 seconds. While Upstox is off or has no
  token, it waits and tries again. It reads the companies and the indices again at each connect.
  `--max-attempts N` stops it after N failed connections in a row. It never saves a guessed price.

The browser opens `wss://<site>/ws/live/quotes/`. Caddy sends it to `realtime`. The Today page
shows a *Live market* strip with the indices, and live prices next to the stocks to watch. The
company page shows the live price, the change, OHLC, volume, the buy and sell pressure and the
market depth. Without live data, the pages show the saved quote.

| Message (server to browser) | Content |
| --- | --- |
| `{"type": "snapshot", "quotes": [...], "status": {...}}` | The newest saved values, sent after connect and after each `subscribe`. |
| `{"type": "quotes", "quotes": [...]}` | Changed quotes, about once a second. |
| `{"type": "status", "status": {"segments": {"NSE_EQ": "NORMAL_OPEN"}}}` | The exchange session state. |
| `{"type": "error", "detail": "..."}` | A message from the browser was not valid. |

The browser sends `{"type": "subscribe", "companies": [1, 2]}` (25 company ids at most) to
follow companies. The indices are always sent. The server closes the socket with code 4401 for a
signed-out user and 4403 for an account without Markets access.

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
