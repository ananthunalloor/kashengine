"""Management command: read the IPO list from the source pages."""

from django.core.management.base import BaseCommand

from apps.ipos.collect import collect_ipos, refresh_statuses
from apps.ipos.scoring import score_ipos
from apps.siteconfig import conf


class Command(BaseCommand):
    """Read the IPO list now, then update the status and the scores."""

    help = (
        "Read the IPO list from the source pages now. Then update the status and the scores. "
        "Set IPO_FETCH_ENABLED=true first (read the note in apps/ipos/sources.py)."
    )

    def add_arguments(self, parser):
        """Add the --force option."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Fetch even if IPO_FETCH_ENABLED is false. For a test run.",
        )

    def handle(self, *args, **options):
        """Run the collection and print the counts."""
        if conf.IPO_FETCH_ENABLED or options["force"]:
            stats = collect_ipos()
            self.stdout.write(
                "IPOs: {created} new, {updated} updated, {unchanged} unchanged, "
                "{skipped} skipped (too old).".format(**stats)
            )
            for error in stats["failed"].values():
                self.stdout.write(self.style.WARNING(f"  Failed: {error}"))
        else:
            self.stdout.write(
                "The fetch is off (IPO_FETCH_ENABLED=false). Only the status and the scores "
                "are updated. Use --force for a test run."
            )
        self.stdout.write(f"Status changed for {refresh_statuses()} IPOs.")
        scores = score_ipos()
        self.stdout.write("Scores: {scored} with a verdict, {unknown} without.".format(**scores))
