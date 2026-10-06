"""Send a report to the Telegram chats and record every try in DeliveryLog."""

import logging

from django.conf import settings

from apps.reports.models import Report

from .models import DeliveryLog
from .telegram import TelegramClient, TelegramError, redact

logger = logging.getLogger(__name__)

ERROR_CHARS = 500


class DeliveryNotConfigured(Exception):
    """The bot token or the chat IDs are not set."""


def configured_chat_ids() -> list[str]:
    return [chat_id.strip() for chat_id in settings.TELEGRAM_CHAT_IDS if chat_id.strip()]


def deliver_report(
    report: Report,
    chat_ids: list[str] | None = None,
    client: TelegramClient | None = None,
    force: bool = False,
) -> dict:
    """Send the report to each chat. Return {"sent", "failed", "skipped", "errors": {chat: text}}.

    A chat that already got this report ("sent" in DeliveryLog) is skipped, so the retry run and a
    second manual run do not send twice. force=True sends to all the chats again.
    One chat that fails does not stop the others.

    A text of more than 4000 characters goes in more than one message. If a later message fails,
    a retry sends all the messages again, so the first one can arrive twice. The report is built to
    be shorter than one message, so this should be rare.
    """
    chat_ids = configured_chat_ids() if chat_ids is None else chat_ids
    if not settings.TELEGRAM_BOT_TOKEN and client is None:
        raise DeliveryNotConfigured("TELEGRAM_BOT_TOKEN is not set.")
    if not chat_ids:
        raise DeliveryNotConfigured("TELEGRAM_CHAT_IDS is empty.")

    result: dict = {"sent": 0, "failed": 0, "skipped": 0, "errors": {}}
    own_client = client is None
    client = client or TelegramClient()
    token = client.token
    try:
        for chat_id in chat_ids:
            already = DeliveryLog.objects.filter(
                report=report,
                channel=DeliveryLog.Channel.TELEGRAM,
                recipient=chat_id,
                status=DeliveryLog.Status.SENT,
            ).exists()
            if already and not force:
                result["skipped"] += 1
                continue
            try:
                client.send_message(chat_id, report.text)
            except TelegramError as exc:
                message = redact(str(exc), token)[:ERROR_CHARS]
                logger.warning("Report %s not sent to %s: %s", report.date, chat_id, message)
                DeliveryLog.objects.create(
                    report=report,
                    channel=DeliveryLog.Channel.TELEGRAM,
                    status=DeliveryLog.Status.FAILED,
                    recipient=chat_id,
                    error=message,
                )
                result["failed"] += 1
                result["errors"][chat_id] = message
            else:
                DeliveryLog.objects.create(
                    report=report,
                    channel=DeliveryLog.Channel.TELEGRAM,
                    status=DeliveryLog.Status.SENT,
                    recipient=chat_id,
                )
                result["sent"] += 1
    finally:
        if own_client:
            client.close()
    logger.info(
        "Report %s: %d sent, %d failed, %d skipped",
        report.date,
        result["sent"],
        result["failed"],
        result["skipped"],
    )
    return result
