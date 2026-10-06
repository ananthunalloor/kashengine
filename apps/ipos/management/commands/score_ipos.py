from django.core.management.base import BaseCommand

from apps.ipos.collect import refresh_statuses
from apps.ipos.models import Ipo
from apps.ipos.scoring import score_ipos


class Command(BaseCommand):
    help = "Update the status of the IPOs, score them, and show the ones that are not listed."

    def handle(self, *args, **options):
        refresh_statuses()
        stats = score_ipos()
        self.stdout.write("Scores: {scored} with a verdict, {unknown} without.".format(**stats))

        rows = Ipo.objects.exclude(status=Ipo.Status.LISTED).exclude(scored_at__isnull=True)
        if not rows.exists():
            self.stdout.write("No IPO to show.")
            return
        self.stdout.write(
            f"{'IPO':<34}{'Status':<10}{'GMP %':>7}{'Subs x':>9}{'Score':>8}  Verdict"
        )
        for ipo in rows.order_by("-score", "name"):
            gmp = "-" if ipo.gmp_pct is None else f"{ipo.gmp_pct:.1f}"
            subs = "-" if ipo.subscription_times is None else f"{ipo.subscription_times:.1f}"
            score = "-" if ipo.score is None else f"{ipo.score:+.2f}"
            self.stdout.write(
                f"{ipo.name[:33]:<34}{ipo.status:<10}{gmp:>7}{subs:>9}{score:>8}  {ipo.verdict}"
            )
        self.stdout.write("The verdict is a rule of thumb, not advice. Check: ipo_stats")
