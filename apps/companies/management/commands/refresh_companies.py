from django.core.management.base import BaseCommand

from apps.companies.screener import refresh_stale


class Command(BaseCommand):
    help = (
        "Refresh company data from Screener.in now. "
        "Read the note at the top of apps/companies/screener.py first. "
        "It works only when SCREENER_ENABLED=true."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "symbols", nargs="*", help="Refresh only these symbols, for example INFY TCS."
        )
        parser.add_argument(
            "--all", action="store_true", help="Refresh all companies, not only old data."
        )
        parser.add_argument("--limit", type=int, help="Maximum number of companies.")

    def handle(self, *args, **options):
        stats = refresh_stale(
            limit=options["limit"],
            symbols=[s.upper() for s in options["symbols"]] or None,
            force=options["all"],
        )
        if stats.get("disabled"):
            self.stdout.write(
                "Screener.in refresh is off. Set SCREENER_ENABLED=true to turn it on."
            )
            return
        self.stdout.write(
            "Screener.in: {refreshed} refreshed, {not_found} not found, {blocked} blocked by "
            "robots.txt, {failed} failed.".format(**stats)
        )
        if stats["stopped_early"]:
            self.stdout.write(self.style.WARNING("Stopped early after many errors in a row."))
