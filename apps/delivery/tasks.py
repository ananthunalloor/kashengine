"""Celery task for the daily report."""

import logging

from celery import shared_task

from apps.markets.trading import is_trading_day, today_ist
from apps.reports.builder import build_report

from .service import (
    DeliveryNotConfiguredError,
    deliver_report,
    deliver_user_emails,
    report_chat_ids,
)

logger = logging.getLogger(__name__)


@shared_task(name="delivery.send_daily_report", soft_time_limit=300)
def send_daily_report() -> dict:
    """Build the report for today and send it. It does nothing when the market is closed.

    The task runs two times in the morning. The second run sends only to Telegram chats and email
    addresses that did not get the report in the first run. A Telegram setup error is recorded in
    the result, and the email delivery still runs.

    Returns:
        A dict for the task result. `skipped` has a text when the market is closed. Else it has
        `date`, `built` (True if this run made the report), the Telegram counts `sent`, `failed`
        and `skipped`, `errors`, `telegram_not_sent` (only when the bot is not set up), and the
        email counts `email_sent`, `email_failed` and `email_skipped`.
    """
    today = today_ist()
    if not is_trading_day(today):
        return {"skipped": "The market is closed today (weekend)."}

    report, created = build_report(today)
    delivery = {"sent": 0, "failed": 0, "skipped": 0, "errors": {}}
    chat_ids = report_chat_ids()
    if chat_ids:
        try:
            delivery = deliver_report(report, chat_ids=chat_ids)
        except DeliveryNotConfiguredError as exc:
            logger.warning("Telegram report %s not sent: %s", report.date, exc)
            delivery["telegram_not_sent"] = str(exc)
    email = deliver_user_emails(report)
    return {
        "date": today.isoformat(),
        "built": created,
        **delivery,
        "email_sent": email["sent"],
        "email_failed": email["failed"],
        "email_skipped": email["skipped"],
    }
