"""Management command: build the report and send it to Telegram."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.delivery.service import DeliveryNotConfiguredError, configured_chat_ids, deliver_report
from apps.delivery.telegram import TelegramClient, TelegramError
from apps.reports.builder import build_report


class Command(BaseCommand):
    """Build the daily report and send it."""

    help = (
        "Build the daily report (if it does not exist) and send it to the Telegram chats in "
        "TELEGRAM_CHAT_IDS. A chat that already got the report is skipped."
    )

    def add_arguments(self, parser):
        """Add the command options."""
        parser.add_argument("--date", help="The date of the report, as YYYY-MM-DD. Default: today.")
        parser.add_argument(
            "--force", action="store_true", help="Send again, also to the chats that got it."
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Send only a short test message. It does not build or save a report.",
        )

    def handle(self, *args, **options):
        """Run the command."""
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
        try:
            result = deliver_report(report, force=options["force"])
        except DeliveryNotConfiguredError as exc:
            raise CommandError(
                f"{exc} Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS in your .env file. "
                "Run telegram_check to find your chat ID."
            ) from exc

        self.stdout.write(
            "Telegram: {sent} sent, {failed} failed, {skipped} skipped.".format(**result)
        )
        for chat_id, error in result["errors"].items():
            self.stdout.write(self.style.WARNING(f"  {chat_id}: {error}"))
        if result["failed"]:
            raise CommandError("Some chats did not get the report. Run the command again.")

    def _send_test(self):
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
