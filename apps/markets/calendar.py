"""Presentation of the staff-maintained NSE cash/equity trading calendar."""

from datetime import UTC, datetime, timedelta

from django.utils import timezone

from .models import TradingCalendarDay
from .trading import is_trading_day, market_tz, session_close, session_open

SOURCE_URL = "https://www.nseindia.com/resources/exchange-communication-holidays"


def calendar_snapshot(year: int, now: datetime | None = None) -> dict:
    """Return the saved calendar exceptions of a year and the scheduled market status now.

    The status comes from the saved calendar and the regular hours. It is not a live feed from
    the exchange.

    Args:
        year: The calendar year of the `days` list.
        now: The time to use as the current time. The default is the current time.

    Returns:
        A dict with `year`, `as_of`, `next_change_at` (the next open or close boundary, or
        midnight), `is_open`, `status_key`, `reason`, `special_reason`, `source_url` and `days`
        (the saved holidays and special sessions of the year).
    """
    local = (now or timezone.now()).astimezone(market_tz())
    day = local.date()
    exception = TradingCalendarDay.objects.filter(day=day).first()
    trading = is_trading_day(day)
    opening, closing = session_open(day), session_close(day)
    is_open = trading and opening <= local < closing
    if not trading:
        reason = exception.reason if exception else "Weekend"
    elif local < opening:
        reason = f"Today's session starts at {opening:%H:%M} IST."
    elif local >= closing:
        reason = f"Today's session ended at {closing:%H:%M} IST."
    else:
        reason = exception.reason if exception else "Regular trading session"
    # Refresh at the next boundary, even if the tab remains open overnight.
    next_change = datetime.combine(day + timedelta(days=1), datetime.min.time(), market_tz())
    for boundary in (opening, closing):
        if trading and local < boundary < next_change:
            next_change = boundary
    return {
        "year": year,
        "as_of": local.astimezone(UTC),
        "next_change_at": next_change.astimezone(UTC),
        "is_open": is_open,
        "status_key": f"{day}:{is_open}:{reason}",
        "reason": reason,
        "special_reason": exception.reason if trading and exception else "",
        "source_url": SOURCE_URL,
        "days": [
            {
                "day": row.day,
                "kind": row.kind,
                "reason": row.reason,
                "opens_at": row.opens_at.strftime("%H:%M") if row.opens_at else "",
                "closes_at": row.closes_at.strftime("%H:%M") if row.closes_at else "",
                "source_url": row.source_url,
            }
            for row in TradingCalendarDay.objects.filter(day__year=year)
        ],
    }
