"""Management command: show how good the IPO verdicts were."""

from django.core.management.base import BaseCommand

from apps.ipos.scoring import MIN_RESULTS_TO_TRUST, ipo_stats


class Command(BaseCommand):
    """Print the result of the verdicts against the baseline."""

    help = "Show how good the IPO verdicts were, and compare them with a simple baseline."

    def handle(self, *args, **options):
        """Print the statistics."""
        stats = ipo_stats()
        self.stdout.write(
            f"Listed IPOs with a result: {stats['listed']}   "
            f"With a verdict before the listing: {stats['judged']}   "
            f"Not listed yet: {stats['pending']}"
        )
        if not stats["listed"]:
            self.stdout.write("No results yet. A result comes after an IPO lists.")
            return

        self.stdout.write(
            f"Baseline: {stats['baseline'] * 100:.0f}% of all listed IPOs did well "
            "(the listing gain reached the limit)."
        )
        for verdict, part in stats["by_verdict"].items():
            if not part["n"]:
                self.stdout.write(f"  {verdict:<6} no results")
                continue
            self.stdout.write(
                f"  {verdict:<6} {part['did_well']}/{part['n']} did well "
                f"({part['did_well'] / part['n'] * 100:.0f}%), "
                f"average gain {part['average_gain']:+.1f}%"
            )
        if not stats["enough_results"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Only {stats['judged']} IPOs with a verdict. Wait for at least "
                    f"{MIN_RESULTS_TO_TRUST} before you trust these numbers."
                )
            )
        else:
            good = stats["by_verdict"]["good"]
            if good["n"] and good["did_well"] / good["n"] <= stats["baseline"]:
                self.stdout.write(self.style.WARNING('"Good" IPOs do not beat the baseline yet.'))
