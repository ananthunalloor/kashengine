"""Celery tasks for news collection."""

import logging

from celery import shared_task

from apps.companies.tasks import link_news
from apps.siteconfig import conf

from .rss import fetch_all_feeds
from .scraper import scrape_pending
from .sentiment import score_pending

logger = logging.getLogger(__name__)


@shared_task(name="news.fetch_feeds", soft_time_limit=600)
def fetch_feeds() -> dict:
    """Read all RSS feeds. Then start the next steps for the new articles.

    The steps are: link the companies, scrape the full text, and score the sentiment.
    The scoring starts after the scrape, so it can use the full text.
    """
    result = fetch_all_feeds()
    logger.info(
        "News fetch done: %d new articles, %d feeds failed", result["new"], len(result["failed"])
    )
    if result["new"]:
        link_news.delay()  # Link the new articles to the companies that they name.
        if conf.NEWS_SCRAPE_FULL_TEXT:
            scrape_articles.delay()  # This task starts the scoring when it is done.
        else:
            score_articles.delay()
    return result


@shared_task(name="news.scrape_articles", soft_time_limit=1800)
def scrape_articles(limit: int | None = None) -> dict:
    """Download the full text for articles that have none. Then start the scoring."""
    result = scrape_pending(limit=limit)
    logger.info("News scrape done: %s", result)
    score_articles.delay()
    return result


@shared_task(name="news.score_articles", soft_time_limit=3300)
def score_articles(limit: int | None = None) -> dict:
    """Score the sentiment of the articles that are not scored yet, with the local LLM."""
    result = score_pending(limit=limit)
    logger.info("News scoring done: %s", result)
    return result
