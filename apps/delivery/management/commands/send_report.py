"""Management command: build the report and send it to opted-in destinations."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.delivery.service import (
    DeliveryNotConfiguredError,
    DeliveryResult,
    configured_chat_ids,
    deliver_report,
    deliver_user_emails,
    report_chat_ids,
)
from apps.delivery.telegram import TelegramClient, TelegramError
from apps.reports.builder import build_report


class Command(BaseCommand):
    """Build the daily report and send it."""

    help = (
        "Build the daily report (if it does not exist) and send it to the Telegram chats in "
        "TELEGRAM_CHAT_IDS and opted-in user destinations. Destinations that already got it are "
        "skipped."
    )

    def add_arguments(self, parser):
        """Add the command options `--date`, `--force` and `--test`.

        Args:
            parser: The parser of the command.
        """
        parser.add_argument("--date", help="The date of the report, as YYYY-MM-DD. Default: today.")
        parser.add_argument(
            "--force", action="store_true", help="Send again to destinations that got it already."
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Send only a short test message. It does not build or save a report.",
        )

    def handle(self, *args, **options):
        """Build the report and send it, or send a test message with `--test`.

        The command prints how many chats got the report. It prints each failed chat with a
        safe error text.

        Args:
            args: Positional arguments. The command has none.
            options: The parsed options: `date`, `force` and `test`.

        Raises:
            CommandError: If the date is not valid, if the bot token or the chat IDs are not
                set, or if a chat did not get the report. Run the command again in that case.
        """
        if options["test"]:
            self._send_test()
            return

        day = None
        if options["date"]:
            try:
                day = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError("Use the date format YYYY-MM-DD.") from exc

        report, created = build_report(day)
        self.stdout.write(f"Report {report.date}: {'built' if created else 'exists'}.")
        telegram: DeliveryResult = {"sent": 0, "failed": 0, "skipped": 0, "errors": {}}
        telegram_error = ""
        chat_ids = report_chat_ids()
        if chat_ids:
            try:
                telegram = deliver_report(report, chat_ids=chat_ids, force=options["force"])
            except DeliveryNotConfiguredError as exc:
                telegram_error = str(exc)

        email = deliver_user_emails(report, force=options["force"])
        if not chat_ids and not any(email[key] for key in ("sent", "failed", "skipped")):
            raise CommandError("No Telegram chats or opted-in email destinations are configured.")
        if telegram_error:
            self.stdout.write(self.style.WARNING(f"Telegram not sent: {telegram_error}"))
        elif chat_ids:
            self.stdout.write(
                "Telegram: {sent} sent, {failed} failed, {skipped} skipped.".format(**telegram)
            )
        self.stdout.write("Email: {sent} sent, {failed} failed, {skipped} skipped.".format(**email))
        for result in (telegram, email):
            for recipient, error in result["errors"].items():
                self.stdout.write(self.style.WARNING(f"  {recipient}: {error}"))
        if telegram["failed"] or email["failed"] or telegram_error:
            raise CommandError(
                "Some report destinations did not get the report. Run the command again."
            )

    def _send_test(self):
        """Send a short test message to each configured chat. No report is built or saved.

        Raises:
            CommandError: If no chat ID is set, or if Telegram refuses a message.
        """
        chat_ids = configured_chat_ids()
        if not chat_ids:
            raise CommandError("TELEGRAM_CHAT_IDS is empty. Run telegram_check to find your ID.")
        try:
            with TelegramClient() as client:
                for chat_id in chat_ids:
                    client.send_message(chat_id, "Kash Engine: this is a test message.")
                    self.stdout.write(f"Test message sent to {chat_id}.")
        except TelegramError as exc:
            raise CommandError(str(exc)) from exc
