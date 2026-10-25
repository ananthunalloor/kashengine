"""Send a report by Telegram and by email, and record every try in DeliveryLog."""

import logging
import smtplib
from typing import TypedDict

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from apps.reports.models import Report
from apps.siteconfig import conf

from .models import DeliveryLog, DeliveryPreference
from .telegram import TelegramClient, TelegramError, redact

logger = logging.getLogger(__name__)

ERROR_CHARS = 500


class DeliveryResult(TypedDict):
    """Counts and per-recipient errors from a delivery attempt."""

    sent: int
    failed: int
    skipped: int
    errors: dict[str, str]


class DeliveryNotConfiguredError(Exception):
    """The bot token or the chat IDs are not set."""


def configured_chat_ids() -> list[str]:
    """Return the chat IDs from the settings, without blank values.

    Returns:
        The chat IDs as trimmed texts, in the order of the setting `TELEGRAM_CHAT_IDS`.
    """
    return [chat_id.strip() for chat_id in conf.TELEGRAM_CHAT_IDS if chat_id.strip()]


def report_chat_ids() -> list[str]:
    """Return the Telegram chats that get the daily report.

    The list has the chats of the setting `TELEGRAM_CHAT_IDS` and the linked chats of users who
    turned on Telegram reports. A user chat counts only if the user is active and has a verified
    email. Staff and superusers do not need a verified email.

    Returns:
        The chat IDs as texts, without duplicates. The chats of the setting come first.
    """
    user_chat_ids = (
        DeliveryPreference.objects.filter(
            telegram_reports=True, telegram_chat_id__isnull=False, user__is_active=True
        )
        .filter(
            Q(email_verified_at__isnull=False) | Q(user__is_staff=True) | Q(user__is_superuser=True)
        )
        .values_list("telegram_chat_id", flat=True)
    )
    return list(dict.fromkeys([*configured_chat_ids(), *user_chat_ids]))


def deliver_user_emails(report: Report, force: bool = False) -> DeliveryResult:
    """Email a report to active users who verified and enabled email delivery.

    One address that fails does not stop the others. Each try writes a `DeliveryLog` row with
    the channel `email`.

    Args:
        report: The report to email.
        force: Send again even when a successful delivery is already logged.

    Returns:
        A dict with the counts `sent`, `failed` and `skipped`, and `errors` (a dict from the email
        address to a safe error text of at most 500 characters).

    Side effects:
        Sends email messages. Writes one `DeliveryLog` row for each address that is tried.
    """
    result: DeliveryResult = {"sent": 0, "failed": 0, "skipped": 0, "errors": {}}
    preferences = (
        DeliveryPreference.objects.filter(
            email_reports=True,
            email_verified_at__isnull=False,
            user__is_active=True,
        )
        .exclude(Q(user__email="") | Q(user__email__isnull=True))
        .select_related("user")
    )
    for preference in preferences:
        email = preference.user.email
        already = DeliveryLog.objects.filter(
            report=report,
            channel=DeliveryLog.Channel.EMAIL,
            recipient=email,
            status=DeliveryLog.Status.SENT,
        ).exists()
        if already and not force:
            result["skipped"] += 1
            continue
        try:
            sent = send_mail(
                subject=f"Kash Engine daily report — {report.date:%d %b %Y}",
                message=report.text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except (OSError, smtplib.SMTPException) as exc:
            message = str(exc)
        else:
            message = "" if sent else "The email backend did not accept the message."
        if message:
            message = message[:ERROR_CHARS]
            logger.warning("Report %s not emailed to %s: %s", report.date, email, message)
            DeliveryLog.objects.create(
                report=report,
                channel=DeliveryLog.Channel.EMAIL,
                status=DeliveryLog.Status.FAILED,
                recipient=email,
                error=message,
            )
            result["failed"] += 1
            result["errors"][email] = message
        else:
            DeliveryLog.objects.create(
                report=report,
                channel=DeliveryLog.Channel.EMAIL,
                status=DeliveryLog.Status.SENT,
                recipient=email,
            )
            result["sent"] += 1
    return result


def deliver_report(
    report: Report,
    chat_ids: list[str] | None = None,
    client: TelegramClient | None = None,
    force: bool = False,
) -> DeliveryResult:
    """Send the report to each Telegram chat and write one `DeliveryLog` row for each try.

    A chat that already got this report ("sent" in DeliveryLog) is skipped, so the retry run and a
    second manual run do not send twice. force=True sends to all the chats again.
    One chat that fails does not stop the others.

    A text of more than 4000 characters goes in more than one message. If a later message fails,
    a retry sends all the messages again, so the first one can arrive twice. The report is built to
    be shorter than one message, so this should be rare.

    Args:
        report: The report to send. The function sends `report.text`.
        chat_ids: The chat IDs. The default is the chat IDs of the settings.
        client: A Telegram client. The default is a new client that the function closes at the
            end. Tests give a fake client.
        force: If True, send to all chats, also to chats that already got this report.

    Returns:
        A `DeliveryResult` dict with the keys `sent`, `failed` and `skipped` (counts of chats) and
        `errors` (a dict from the chat ID to a safe error text, without the bot token and at most
        500 characters).

    Raises:
        DeliveryNotConfiguredError: If the bot token is not set (and no client is given), or if
            there is no chat ID.

    Side effects:
        Sends messages to Telegram. Writes one `DeliveryLog` row for each chat that is tried.
    """
    chat_ids = configured_chat_ids() if chat_ids is None else chat_ids
    if not conf.TELEGRAM_BOT_TOKEN and client is None:
        raise DeliveryNotConfiguredError("TELEGRAM_BOT_TOKEN is not set.")
    if not chat_ids:
        raise DeliveryNotConfiguredError("TELEGRAM_CHAT_IDS is empty.")

    result: DeliveryResult = {"sent": 0, "failed": 0, "skipped": 0, "errors": {}}
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
