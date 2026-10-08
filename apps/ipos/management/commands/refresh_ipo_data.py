"""Management command: refresh the GMP, subscription, and listing results."""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ipos.collect import refresh_statuses
from apps.ipos.gmp import SAMPLE_SIZE, GmpSourceError, update_gmp
from apps.ipos.listing import fill_listing_results, listing_candidates
from apps.ipos.scoring import score_ipos
from apps.markets.trading import today_ist


class Command(BaseCommand):
    """Run the GMP and listing steps now, then update the status and the scores."""

    help = (
        "Read the GMP and the subscription from the live table, and get the listing price of the "
        "IPOs that listed lately. Then update the status and the scores. Use this to test the "
        "sources. Read the notes in apps/ipos/gmp.py and apps/ipos/listing.py first."
    )

    def add_arguments(self, parser):
        """Add the --force and --save-page options."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run a step also when its setting is off (IPO_GMP_ENABLED, IPO_LISTING_ENABLED).",
        )
        parser.add_argument(
            "--save-page",
            metavar="FILE",
            help="Write the GMP page to this file. Send it to us if the parser fails.",
        )

    def handle(self, *args, **options):
        """Run the steps and print what each one did."""
        force = options["force"]

        if settings.IPO_GMP_ENABLED or force:
            self.stdout.write(f"GMP page: {settings.IPO_GMP_URL}")
            try:
                result = update_gmp(save_page_to=options["save_page"])
            except GmpSourceError as exc:
                self.stdout.write(self.style.ERROR(f"  Failed: {exc}"))
            else:
                self.stdout.write(
                    f"  {result.rows} rows. {result.matched} match a saved IPO: "
                    f"{result.updated} updated, {result.unchanged} unchanged, "
                    f"{result.older} older than our value, {result.suspect} suspect."
                )
                if result.unmatched:
                    sample = ", ".join(result.unmatched[:SAMPLE_SIZE])
                    self.stdout.write(
                        f"  {len(result.unmatched)} rows match no saved IPO (old IPOs, or IPOs "
                        f"that we do not have). For example: {sample}"
                    )
                if result.matched == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            "  No row matched. Collect the IPO list first (collect_ipos), or "
                            "check the names above."
                        )
                    )
        else:
            self.stdout.write("The GMP fetch is off (IPO_GMP_ENABLED=false). Use --force to test.")

        if settings.IPO_LISTING_ENABLED or force:
            today = today_ist()
            waiting = listing_candidates(today).count()
            stats = fill_listing_results(today)
            self.stdout.write(
                f"Listing results: {stats['filled']} filled, {stats['waiting']} without a price "
                f"yet, {stats['no_code']} without an exchange code (of {waiting} IPOs checked)."
            )
        else:
            self.stdout.write("The listing step is off (IPO_LISTING_ENABLED=false).")

        self.stdout.write(f"Status changed for {refresh_statuses()} IPOs.")
        scores = score_ipos()
        self.stdout.write("Scores: {scored} with a verdict, {unknown} without.".format(**scores))
