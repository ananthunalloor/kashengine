"""Small helpers for the IPO tests."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from apps.ipos.models import Ipo

IST = ZoneInfo("Asia/Kolkata")

TODAY = date(2026, 10, 5)  # A Monday.
NOW = datetime(2026, 10, 5, 8, 0, tzinfo=IST)


def make_ipo(name: str = "Acme Foods Limited", **kwargs) -> Ipo:
    kwargs.setdefault("open_date", TODAY)
    kwargs.setdefault("close_date", TODAY + timedelta(days=2))
    kwargs.setdefault("price_band_high", Decimal("100"))
    return Ipo.objects.create(name=name, **kwargs)


def set_stamps(ipo: Ipo, gmp_at=NOW, subscription_at=NOW) -> Ipo:
    """Set the GMP and subscription times without the automatic change in Ipo.save()."""
    Ipo.objects.filter(pk=ipo.pk).update(
        gmp_updated_at=gmp_at, subscription_updated_at=subscription_at
    )
    ipo.refresh_from_db()
    return ipo
