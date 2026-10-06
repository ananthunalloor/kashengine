from django.core.management.base import BaseCommand, CommandError

from apps.ipos.collect import CSV_COLUMNS, import_csv, refresh_statuses
from apps.ipos.scoring import score_ipos


class Command(BaseCommand):
    help = (
        "Save IPOs from a CSV file. Use it for the GMP and the subscription, or when the fetch "
        f"is off. Columns: {CSV_COLUMNS}. Only 'name' is required. An empty cell changes nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="The CSV file.")

    def handle(self, *args, **options):
        try:
            stats = import_csv(options["path"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            "IPOs: {created} new, {updated} updated, {unchanged} unchanged, "
            "{skipped} skipped (too old).".format(**stats)
        )
        refresh_statuses()
        scores = score_ipos()
        self.stdout.write("Scores: {scored} with a verdict, {unknown} without.".format(**scores))
