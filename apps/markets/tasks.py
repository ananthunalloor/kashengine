"""Celery tasks for market data and the prediction.

Celery beat runs the two tasks on schedules that the Ops pages keep (the defaults are in
`apps/ops/defaults.py`). `markets.fetch_quotes` downloads the quotes and checks the
old predictions. `markets.predict` makes the prediction for the day. The tasks call
`quotes.fetch_quotes`, `evaluation.evaluate_pending` and `prediction.make_prediction`. Each task
returns a dict that Celery keeps as the task result.
"""

import logging

from celery import shared_task

from .evaluation import evaluate_pending
from .prediction import make_prediction
from .quotes import fetch_quotes as fetch_all_quotes
from .trading import is_trading_day, today_ist

logger = logging.getLogger(__name__)


@shared_task(name="markets.fetch_quotes", soft_time_limit=600)
def fetch_quotes() -> dict:
    """Download the quotes. Then check the predictions that have no result yet.

    The task has a soft time limit of 600 seconds. It first calls `quotes.fetch_quotes`. Then it
    calls `evaluation.evaluate_pending`, so a new final quote can close a prediction at once.

    Returns:
        The dict from `quotes.fetch_quotes` (`saved` and `failed`) with one more key,
        `evaluation`. That key holds the dict from `evaluate_pending`.

    Side effects:
        Network calls to Yahoo Finance. Writes to the `IndexQuote` and `Prediction` tables.
    """
    result = fetch_all_quotes()
    result["evaluation"] = evaluate_pending()
    logger.info("Market quotes task done: %s", result)
    return result


@shared_task(name="markets.predict", soft_time_limit=300)
def predict() -> dict:
    """Make the prediction for today, unless the saved calendar has no session.

    The task has a soft time limit of 300 seconds. On a weekday it calls
    `prediction.make_prediction` with the default target. If a prediction for the day exists
    already, the function returns it and does not change it.

    Returns:
        On a weekend, a dict with the key `skipped` and a text. On a weekday, a dict with
        `target_date` (an ISO date text), `direction`, `confidence` and `created`. `created` is
        False when the prediction existed already.

    Side effects:
        Can create a row in the `Prediction` table.

    Saved holidays and special weekend sessions override the regular weekday schedule.
    """
    today = today_ist()
    if not is_trading_day(today):
        return {"skipped": "The market is closed today (weekend or saved holiday)."}
    prediction, created = make_prediction()
    return {
        "target_date": prediction.target_date.isoformat(),
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "created": created,
    }
