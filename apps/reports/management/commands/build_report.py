from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.reports.builder import build_report


class Command(BaseCommand):
    help = (
        "Build the daily report and show the text. It is saved, but not sent "
        "(use send_report for that)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", help="The date of the report, as YYYY-MM-DD. Default: today.")
        parser.add_argument(
            "--force", action="store_true", help="Build it again, even if the report exists."
        )

    def handle(self, *args, **options):
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
