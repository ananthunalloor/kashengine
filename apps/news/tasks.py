"""Celery tasks for news collection."""

import logging

from celery import shared_task
from django.conf import settings

from .rss import fetch_all_feeds
from .scraper import scrape_pending

logger = logging.getLogger(__name__)


@shared_task(name="news.fetch_feeds", soft_time_limit=600)
def fetch_feeds() -> dict:
    """Read all RSS feeds. Then start the full-text scrape for the new articles."""
    result = fetch_all_feeds()
    logger.info(
        "News fetch done: %d new articles, %d feeds failed", result["new"], len(result["failed"])
    )
    if settings.NEWS_SCRAPE_FULL_TEXT and result["new"]:
        scrape_articles.delay()
    return result


@shared_task(name="news.scrape_articles", soft_time_limit=1800)
def scrape_articles(limit: int | None = None) -> dict:
    """Download the full text for articles that have none."""
    result = scrape_pending(limit=limit)
    logger.info("News scrape done: %s", result)
    return result
