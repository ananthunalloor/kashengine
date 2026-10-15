"""Management command: build the daily report and print it."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.reports.builder import build_report


class Command(BaseCommand):
    """Build the daily report for one date, save it, and print its text.

    The command calls `apps.reports.builder.build_report`. It does not send the report. The
    `send_report` command of the delivery app builds and sends it.
    """

    help = (
        "Build the daily report and show the text. It is saved, but not sent "
        "(use send_report for that)."
    )

    def add_arguments(self, parser):
        """Add the command options.

        Args:
            parser: The argument parser of the command. The method adds `--date` (a date as
                `YYYY-MM-DD`) and `--force` (a flag).
        """
        parser.add_argument("--date", help="The date of the report, as YYYY-MM-DD. Default: today.")
        parser.add_argument(
            "--force", action="store_true", help="Build it again, even if the report exists."
        )

    def handle(self, *args, **options):
        """Build the report and print the result.

        If the report for the date exists and `--force` is not set, the command prints a message
        and then prints the saved text without a change.

        Args:
            args: Not used.
            options: The parsed options. `date` is a text such as `2026-10-14` or `None`. `None`
                means today in IST. `force` is True when the report must be built again.

        Raises:
            CommandError: If `date` is not in the format `YYYY-MM-DD`.

        Side effects:
            Can create or replace the `Report` row for the date. Can create the `Prediction`
            row and update the IPO rows. Prints to the standard output.
        """
        day = None
        if options["date"]:
            try:
                day = date.fromisoformat(options["date"])
            except ValueError as exc:
                raise CommandError("Use the date format YYYY-MM-DD.") from exc

        report, created = build_report(day, force=options["force"])
        if not created:
            self.stdout.write(
                "The report for this day exists already, and it is not changed. "
                "Use --force to build it again."
            )
        self.stdout.write(f"--- Report {report.date} ({len(report.text)} characters) ---")
        self.stdout.write(report.text)
