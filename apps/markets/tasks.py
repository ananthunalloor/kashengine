"""Celery tasks for market data and the prediction.

Celery beat runs the two tasks on schedules that the Ops pages keep (the defaults are in
`apps/ops/defaults.py`). `markets.fetch_quotes` downloads the quotes and checks the
old predictions. `markets.predict` makes the prediction for the day. The tasks call
`quotes.fetch_quotes`, `evaluation.evaluate_pending` and `prediction.make_prediction`. Each task
returns a dict that Celery keeps as the task result.
"""

import logging

from celery import shared_task
from django.utils import timezone

from apps.companies.outlook import save_outlook
from apps.siteconfig import conf

from .evaluation import evaluate_pending
from .index_constituents import refresh_index_constituents
from .instrument_master import refresh_instruments
from .prediction import make_prediction
from .quotes import fetch_quotes as fetch_all_quotes
from .trading import is_trading_day, session_close, session_open, today_ist
from .upstox import mapped_companies, sync_companies, sync_ipos, sync_news, sync_quotes
from .upstox_client import UpstoxClient

logger = logging.getLogger(__name__)


@shared_task(name="markets.refresh_instruments", soft_time_limit=600)
def refresh_instrument_master() -> dict:
    """Refresh the daily NSE/BSE equity, index, futures, and options catalog.

    The source is Upstox's public instrument master; no access token is required. Any download or
    validation failure is raised so the task run is recorded as failed rather than as a partial
    success.
    """
    result = refresh_instruments()
    logger.info("Exchange instrument catalog refreshed: %s", result)
    return result


@shared_task(name="markets.refresh_index_constituents", soft_time_limit=600)
def refresh_index_memberships() -> dict:
    """Refresh official Nifty index membership without hiding provider failures."""
    result = refresh_index_constituents()
    logger.info("Nifty index constituents refreshed: %s", result)
    return result


@shared_task(name="markets.upstox_quotes", soft_time_limit=240)
def upstox_quotes() -> dict:
    """Save a snapshot quote of each Upstox company, during a trading session only.

    The task needs the setting `UPSTOX_ENABLED`. It uses the trading calendar, so it also runs in a
    saved special session on a weekend.

    Returns:
        A dict with `skipped` and a reason when Upstox is off or the market is closed. Else
        `saved` (the count of new quotes) and `failed` (a dict from the symbol to a safe error).
    """
    if not conf.UPSTOX_ENABLED:
        return {"skipped": "Upstox is disabled."}
    now = timezone.now()
    day = today_ist(now)
    if not is_trading_day(day) or not session_open(day) <= now <= session_close(day):
        return {"skipped": "Outside the saved trading session."}
    with UpstoxClient() as client:
        return sync_quotes(client)


@shared_task(name="markets.upstox_refresh", soft_time_limit=1800)
def upstox_refresh() -> dict:
    """Download company history, fundamentals, news and IPOs from Upstox, then score them.

    The task needs the setting `UPSTOX_ENABLED`. Each part can fail on its own and the task still
    saves the other parts. New news articles start the scoring task. The task then updates the
    IPO scores and the saved outlook of each company.

    Returns:
        A dict with `skipped` when Upstox is off. Else the results `companies`, `news`, `ipos` and
        `ipo_scores`.
    """
    if not conf.UPSTOX_ENABLED:
        return {"skipped": "Upstox is disabled."}
    from apps.ipos.scoring import score_ipos  # noqa: PLC0415
    from apps.news.tasks import score_articles  # noqa: PLC0415

    with UpstoxClient() as client:
        result = {
            "companies": sync_companies(client),
            "news": sync_news(client),
            "ipos": sync_ipos(client),
        }
    result["ipo_scores"] = score_ipos()
    if result["news"]["new"]:
        score_articles.delay()
    for company in mapped_companies():
        save_outlook(company)
    return result


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
