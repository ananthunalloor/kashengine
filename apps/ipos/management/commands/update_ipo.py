from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.ipos.collect import refresh_statuses
from apps.ipos.models import Ipo
from apps.ipos.scoring import score_ipo


def _decimal(value: str | None, option: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise CommandError(f"--{option} must be a number: {value!r}") from exc


class Command(BaseCommand):
    help = (
        "Set the GMP, the subscription, or the listing price of one IPO. Then score it again. "
        'Example: update_ipo "Acme Foods" --gmp 40 --subscription 52.3'
    )

    def add_arguments(self, parser):
        parser.add_argument("name", help="Part of the IPO name. It must match one IPO.")
        parser.add_argument("--gmp", help="Grey market premium in rupees (can be negative).")
        parser.add_argument("--subscription", help="Total subscription, in times.")
        parser.add_argument("--listing-price", help="Price at the listing, in rupees.")

    def handle(self, *args, **options):
        gmp = _decimal(options["gmp"], "gmp")
        subscription = _decimal(options["subscription"], "subscription")
        listing_price = _decimal(options["listing_price"], "listing-price")
        if gmp is None and subscription is None and listing_price is None:
            raise CommandError("Give at least one of --gmp, --subscription, --listing-price.")

        matches = Ipo.objects.filter(name__icontains=options["name"])
        open_ones = matches.exclude(status=Ipo.Status.LISTED)
        if listing_price is None and open_ones.exists():
            matches = open_ones  # A GMP or a subscription is for an IPO that is not listed.
        names = list(matches.values_list("name", flat=True)[:10])
        if not names:
            raise CommandError(f"No IPO has {options['name']!r} in its name.")
        if len(names) > 1:
            raise CommandError("More than one IPO matches: " + ", ".join(names))

        ipo = matches.get()
        now = timezone.now()
        if gmp is not None:
            ipo.gmp = gmp
            ipo.gmp_updated_at = now  # An entry confirms the value, also when it did not change.
        if subscription is not None:
            ipo.subscription_times = subscription
            ipo.subscription_updated_at = now
        if listing_price is not None:
            ipo.listing_price = listing_price
        ipo.save()
        refresh_statuses()
        ipo.refresh_from_db()

        self.stdout.write(f"Saved: {ipo.name}")
        if ipo.status == Ipo.Status.LISTED:
            gain = "-" if ipo.listing_gain_pct is None else f"{ipo.listing_gain_pct:+.1f}%"
            self.stdout.write(f"  Listed. Gain at the listing: {gain}")
            return
        outcome = score_ipo(ipo)
        score = "-" if outcome.score is None else f"{outcome.score:+.2f}"
        self.stdout.write(f"  Verdict now: {outcome.verdict} (score {score})")
        for note in outcome.notes:
            self.stdout.write(self.style.WARNING(f"  Note: {note}"))
        self.stdout.write("  The daily scoring run saves the score. Or run: score_ipos")
