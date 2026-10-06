"""Celery tasks for IPOs."""

import logging

from celery import shared_task
from django.conf import settings

from .collect import collect_ipos, refresh_statuses
from .scoring import score_ipos

logger = logging.getLogger(__name__)


@shared_task(name="ipos.collect", soft_time_limit=300)
def collect() -> dict:
    """Read the IPO list (only if IPO_FETCH_ENABLED), update the status, and score the IPOs."""
    result: dict = {"fetch": "disabled"}
    if settings.IPO_FETCH_ENABLED:
        result["fetch"] = collect_ipos()
    result["status_changed"] = refresh_statuses()
    result["scores"] = score_ipos()
    logger.info("IPO task done: %s", result)
    return result


@shared_task(name="ipos.score", soft_time_limit=120)
def score() -> dict:
    """Update the status and score the IPOs again (for example after new GMP numbers)."""
    refresh_statuses()
    return score_ipos()
