"""Celery tasks for company data."""

import logging

from celery import shared_task
from django.conf import settings

from .matching import link_articles
from .screener import refresh_stale

logger = logging.getLogger(__name__)


@shared_task(name="companies.refresh_stale", soft_time_limit=3600)
def refresh_stale_companies(limit: int | None = None) -> dict:
    """Refresh the Screener.in data of the companies that are older than SCREENER_REFRESH_DAYS.

    The schedule runs this every day. Each company is read only once a week.
    Nothing happens until SCREENER_ENABLED is true.
    """
    if not settings.SCREENER_ENABLED:
        logger.info("Screener.in refresh is off (SCREENER_ENABLED is false).")
        return {"disabled": True}
    result = refresh_stale(limit=limit)
    logger.info("Screener.in refresh done: %s", result)
    return result


@shared_task(name="companies.link_news", soft_time_limit=600)
def link_news(since_hours: int | None = 48) -> dict:
    """Link recent news articles to the companies that they name."""
    return link_articles(since_hours=since_hours)
