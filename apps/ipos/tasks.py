"""Celery tasks for IPOs."""

import logging

from celery import shared_task
from django.conf import settings

from .collect import collect_ipos, refresh_statuses
from .metrics import refresh_metrics
from .scoring import score_ipos

logger = logging.getLogger(__name__)


@shared_task(name="ipos.collect", soft_time_limit=300)
def collect() -> dict:
    """Read the IPO list (only if IPO_FETCH_ENABLED). Then refresh the numbers and the scores."""
    result: dict = {"fetch": "disabled"}
    if settings.IPO_FETCH_ENABLED:
        result["fetch"] = collect_ipos()
    result.update(refresh_metrics())
    logger.info("IPO task done: %s", result)
    return result


@shared_task(name="ipos.score", soft_time_limit=120)
def score() -> dict:
    """Update the status and score the IPOs again (for example after new GMP numbers)."""
    refresh_statuses()
    return score_ipos()


@shared_task(name="ipos.refresh_metrics", soft_time_limit=300)
def refresh_ipo_metrics() -> dict:
    """Read the GMP and the subscription (if IPO_GMP_ENABLED), and get new listing results."""
    result = refresh_metrics()
    logger.info("IPO metrics done: %s", result)
    return result
