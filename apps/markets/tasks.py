"""Celery tasks for market data and the prediction."""

import logging

from celery import shared_task

from .evaluation import evaluate_pending
from .prediction import make_prediction
from .quotes import fetch_quotes as fetch_all_quotes
from .trading import is_trading_day, today_ist

logger = logging.getLogger(__name__)


@shared_task(name="markets.fetch_quotes", soft_time_limit=600)
def fetch_quotes() -> dict:
    """Download the quotes. Then check the predictions that have no result yet."""
    result = fetch_all_quotes()
    result["evaluation"] = evaluate_pending()
    logger.info("Market quotes task done: %s", result)
    return result


@shared_task(name="markets.predict", soft_time_limit=300)
def predict() -> dict:
    """Make the prediction for today. It does nothing on a Saturday or a Sunday."""
    today = today_ist()
    if not is_trading_day(today):
        return {"skipped": "The market is closed today (weekend)."}
    prediction, created = make_prediction()
    return {
        "target_date": prediction.target_date.isoformat(),
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "created": created,
    }
