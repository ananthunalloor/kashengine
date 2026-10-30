"""Price-alert evaluation for saved company quotes."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CompanyPriceAlert, CompanyQuote


def evaluate_price_alerts(quote: CompanyQuote) -> int:
    """Trigger the user's active alerts crossed by this newest saved quote.

    An alert fires only when a later quote moves from below its threshold to at or above it.
    Older or duplicate observations cannot trigger alerts.
    """
    if not CompanyPriceAlert.objects.filter(
        watchlist_entry__company_id=quote.company_id,
        is_active=True,
    ).exists():
        return 0

    with transaction.atomic():
        latest = (
            CompanyQuote.objects.filter(
                company_id=quote.company_id,
                instrument_key=quote.instrument_key,
            )
            .order_by("-as_of", "-pk")
            .first()
        )
        if latest is None or latest.pk != quote.pk:
            return 0

        previous = (
            CompanyQuote.objects.filter(
                company_id=quote.company_id,
                instrument_key=quote.instrument_key,
                as_of__lt=quote.as_of,
            )
            .order_by("-as_of", "-pk")
            .first()
        )
        if previous is None or latest.price <= previous.price:
            return 0

        previous_price = Decimal(str(previous.price))
        current_price = Decimal(str(latest.price))
        alerts = CompanyPriceAlert.objects.select_for_update().filter(
            watchlist_entry__company_id=quote.company_id,
            is_active=True,
        )
        triggered = 0
        now = timezone.now()
        for alert in alerts:
            if previous_price < alert.above_price <= current_price:
                alert.is_active = False
                alert.triggered_at = now
                alert.triggered_price = latest.price
                alert.save(update_fields=["is_active", "triggered_at", "triggered_price"])
                triggered += 1
        return triggered
