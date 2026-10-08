"""Celery task for the daily report."""

import logging

from celery import shared_task

from apps.markets.trading import is_trading_day, today_ist
from apps.reports.builder import build_report

from .service import DeliveryNotConfiguredError, deliver_report

logger = logging.getLogger(__name__)


@shared_task(name="delivery.send_daily_report", soft_time_limit=300)
def send_daily_report() -> dict:
    """Build the report for today and send it. It does nothing on a Saturday or a Sunday.

    The task runs two times in the morning. The second run sends only to the chats that did not
    get the report in the first run.
    """
    today = today_ist()
    if not is_trading_day(today):
        return {"skipped": "The market is closed today (weekend)."}

    report, created = build_report(today)
    try:
        delivery = deliver_report(report)
    except DeliveryNotConfiguredError as exc:
        logger.warning("Report %s is built but not sent: %s", report.date, exc)
        return {"date": today.isoformat(), "built": created, "not_sent": str(exc)}
    return {"date": today.isoformat(), "built": created, **delivery}
