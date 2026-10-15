---
title: News and sentiment
sidebar_label: News
description: How Kash Engine collects news, scrapes article text and scores sentiment with the local LLM.
---

# News and sentiment

Code: `apps/news/`, `apps/llm/`. Tasks: `news.fetch_feeds`, `news.scrape_articles`,
`news.score_articles`.

## Feeds

A feed is a `NewsFeed` row: source, name, URL, an enabled flag and the result of the last run
(`last_fetched_at`, `last_new_count`, `last_error`). The first migration saves the default
feeds. After that, a superuser adds, stops and deletes feeds on **Ops > Feeds**. The code has
no second list.

`fetch_all_feeds` reads each enabled feed with a timeout (`NEWS_REQUEST_TIMEOUT`, 20 seconds) and
the user agent `NEWS_USER_AGENT`. One feed that fails does not stop the others. The result of
each feed is saved, also when no article is new.

An article is unique by its URL. Before the save, the code removes the tracking parameters
(`fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref`, `ref_src`) and the fragment. The title is cut to
500 characters and the summary to 2000. HTML tags are removed from the text.

## Full text

`news.scrape_articles` downloads the page of each article that has no text. The rules:

- **robots.txt first.** The code does not fetch a URL that `robots.txt` forbids.
- **Be polite.** It waits `NEWS_SCRAPE_DELAY_SECONDS` (3 seconds) between requests to one host,
  or the `Crawl-delay` of the site if that is longer.
- **Try once.** An error is final, unless it is temporary (a network error, HTTP 5xx or 429). A
  temporary error is tried again in the next run, until the article is too old
  (`NEWS_SCRAPE_MAX_AGE_HOURS`, 48).
- **Bound the work.** One run takes at most `NEWS_SCRAPE_BATCH_SIZE` (50) articles.
- **Treat the page as untrusted.** The code extracts text. It does not run scripts and does not
  save markup. A text of less than 200 characters counts as "no text".

Set `NEWS_SCRAPE_FULL_TEXT` to false to turn the scrape off. Scoring then uses the title and the
summary.

## Sentiment

`LLMClient` talks to the Ollama server at `LLM_BASE_URL` with the model `LLM_MODEL`. For each
article the model must answer with JSON:

| Field | Meaning |
| --- | --- |
| `score` | From -1 (very bad for Indian stocks) to 1 (very good). |
| `relevance` | From 0 (not about the market) to 1 (can move the whole market). |
| `reason` | One short sentence. The code keeps at most 300 characters. |

The code sends at most `SENTIMENT_MAX_CHARS` (2000) characters of the article. It checks the
answer and cuts values to their range. If the answer is not valid JSON in the right shape, the
client tries once more. Then the article gets one more failed attempt. After
`SENTIMENT_MAX_ATTEMPTS` (3) the article is not tried again. Only articles that are not older
than `SENTIMENT_MAX_AGE_HOURS` (48) are scored.

If the server cannot be reached, or has no such model, the run stops (`stopped: true`). The
articles stay unscored. The code never saves "neutral" for an article that it could not score.

The label `positive`, `neutral` or `negative` is derived from the score with a band of 0.2: a
score of 0.2 or more is positive, -0.2 or less is negative, and the rest is neutral.

### Choose a model

`python manage.py compare_models` scores a fixed set of labelled headlines (`data/sentiment_eval.csv`)
with two or more models. It shows the accuracy, the failures and the time for each item. The set
is small and uses invented names. It shows when a model is clearly bad. It cannot show which of
two good models is better.

## Settings

All settings of this domain are in [Settings](../reference/generated/system/settings.md): the
groups **LLM server**, **News collection** and **Sentiment scoring**.

## Change checklist

- Test duplicate articles and repeated fetches.
- Test an empty feed, a missing field, a bad date, a bad encoding, a redirect and an HTTP error.
- Test a timeout of the model, a bad answer and an empty text.
- Keep the result of each feed on **Ops > Feeds**.
- Update the docstrings and this page if a rule changes.
