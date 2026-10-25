---
title: Data flow
sidebar_label: Data flow
description: How data moves from the news feeds to the daily report, and which task does each step.
---

# Data flow

This page follows the data through one day. The task names are the registered Celery names. The
times are the default schedule (IST). See [Schedule](../reference/generated/system/schedule.md)
for the live list, and [Tasks](../reference/generated/system/tasks.md) for the time limits.

```text
 news.fetch_feeds ─┬─► companies.link_news
   (RSS, every 3 h) └─► news.scrape_articles ──► news.score_articles
                                                         │
                                                         ▼
 markets.fetch_quotes (06:45) ─► markets.predict (07:00) ◄─ scored news
                                                  │
 ipos.collect (06:15, 18:45) ─► ipos.refresh_metrics (07:00 to 19:00, every 2 h)
                                                  │
                                         ipos.score (07:10)
                                                  ▼
                       delivery.send_daily_report (07:30, retry 07:50)
                         builds the report, sends it on Telegram and by email
```

## Step by step

1. **Read the feeds.** `news.fetch_feeds` reads every enabled `NewsFeed` row. One feed that
   fails is logged and skipped. A new article is saved once: its URL is cleaned of tracking
   parameters, and the URL is unique. Each feed keeps the time, the number of new articles and
   the error of its last run.
2. **Link companies.** When a fetch saves new articles, it starts `companies.link_news`. The
   matcher looks for company names and aliases in the title and the summary, as whole words.
3. **Scrape the text.** At the same time the fetch starts `news.scrape_articles`. It downloads
   the full text of articles that have none. It obeys `robots.txt` and waits between requests
   to one host. If `NEWS_SCRAPE_FULL_TEXT` is off, the fetch starts the scoring directly.
4. **Score the sentiment.** `news.score_articles` starts when the scrape is done. It also runs
   every hour at minute 20. It sends each article to the local LLM. The model returns a `score`
   (-1 to 1), a `relevance` (0 to 1) and a short reason. The result is saved on the article.
5. **Get quotes.** `markets.fetch_quotes` saves the daily close and the change in percent of the
   Nifty 50 and of the global cues. It then checks the predictions that have no result yet.
6. **Predict.** `markets.predict` combines the news score and the global score into a score for
   the next trading day, and saves a `Prediction`.
7. **Collect and score IPOs.** `ipos.collect` and `ipos.refresh_metrics` keep the IPO rows
   current. `ipos.score` scores the IPOs that did not list yet.
   If Upstox is on, `markets.upstox_quotes` (every 5 minutes, in a trading session) and
   `markets.upstox_refresh` (every 6 hours) add company quotes, history, fundamentals, news and
   IPOs. A new article goes to the same scoring step. See
   [Upstox data](../domains/markets-and-predictions.md#upstox-data).
8. **Build and send the report.** `delivery.send_daily_report` builds the report for today from
   the stored data and sends it to the Telegram chats and to the users who verified their email and turned on email
   reports. A second run at 07:50 sends only to the recipients that did not get it. The task does nothing when the market is closed (a weekend or a saved holiday).
9. **Show the data.** The web pages and the [HTTP API](../api/overview.md) read the stored data.
   They never call a provider.

## Task runs and manual starts

Every task run is saved as a `TaskRun` row with its status, its time, its worker and a safe
result. The Ops pages show the rows. A superuser can start a [job](../reference/generated/system/jobs.md)
by hand. A job that is waiting or running (for less than 30 minutes) cannot start again.

## What happens when a part fails

| Failure | Behavior |
| --- | --- |
| A news feed is down or sends bad XML. | The feed is skipped and its error is saved. The other feeds continue. |
| An article page cannot be fetched. | A temporary error (network, HTTP 5xx or 429) is tried again in the next run. Other errors are not tried again. |
| The LLM server is down. | Scoring stops for this run. The articles stay unscored. They are never shown as neutral. |
| The model gives invalid output. | The call is tried once more. If it fails again, the article gets a failed attempt. After `SENTIMENT_MAX_ATTEMPTS` the article is not tried again. |
| Quotes are missing or old. | The prediction says so in its notes and lowers its confidence. The health check shows a warning. |
| Telegram refuses a message. | The delivery log keeps a `failed` row with a redacted error. The retry run tries the chats that did not get the report. |
| The database cannot give settings. | The settings layer uses the environment values. |
