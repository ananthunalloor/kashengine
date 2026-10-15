"""Trading days and times for the Indian market. All dates use the time zone of the settings.

We have no list of market holidays. A holiday counts as a trading day here. A prediction for a
holiday ends as "void" (see evaluation.py).

The functions are small helpers. `prediction.py`, `evaluation.py`, the report builder, the
delivery task and the Ops health checks all use them. The close time and the wait after the close
come from the site settings `MARKET_CLOSE_TIME` and `MARKET_FINAL_BUFFER_MINUTES`.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.siteconfig import conf
from apps.siteconfig.registry import clean_clock

FIRST_WEEKEND_WEEKDAY = 5  # datetime.weekday(): Monday is 0, Saturday is 5.


def market_tz() -> ZoneInfo:
    """Return the time zone of the market (`TIME_ZONE` in the Django settings).

    Returns:
        A `ZoneInfo` object. The project sets it to Asia/Kolkata (IST).
    """
    return ZoneInfo(settings.TIME_ZONE)


def today_ist(now: datetime | None = None) -> date:
    """Return the date in the market time zone (IST).

    Args:
        now: The time to convert. It must be timezone-aware. The default (None) is the current
            time.

    Returns:
        The calendar date in IST. It can differ from the UTC date.
    """
    return (now or timezone.now()).astimezone(market_tz()).date()


def is_trading_day(day: date) -> bool:
    """Return True when the day is a weekday (Monday to Friday).

    Args:
        day: The date to test.

    Returns:
        True for Monday to Friday, False for Saturday and Sunday. A market holiday on a weekday
        also gives True, because the code has no holiday list.
    """
    return day.weekday() < FIRST_WEEKEND_WEEKDAY  # Monday to Friday.


def next_trading_day(day: date) -> date:
    """Return the day itself if it is a trading day. If not, return the next one.

    Args:
        day: The start date.

    Returns:
        A date that is the same as `day` or later. It is at most 2 days later (a weekend).
    """
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def previous_trading_day(day: date) -> date:
    """Return the last trading day before this day.

    The day itself is never the result, even when it is a trading day.

    Args:
        day: The reference date.

    Returns:
        The nearest earlier weekday. For a Monday, this is the Friday before.
    """
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def session_close(day: date) -> datetime:
    """Return the close time of the market on a day.

    The time comes from the site setting `MARKET_CLOSE_TIME` (format HH:MM, in IST).

    Args:
        day: The date of the session.

    Returns:
        A timezone-aware datetime on `day` at the close time, in the market time zone.
    """
    close = clean_clock(conf.MARKET_CLOSE_TIME)
    return datetime.combine(day, close, tzinfo=market_tz())


def final_buffer() -> timedelta:
    """Return how long after the close Yahoo needs to show the final price.

    The value comes from the site setting `MARKET_FINAL_BUFFER_MINUTES`.

    Returns:
        A `timedelta` in minutes. `evaluation.py` adds it to the close time to find when a
        quote is final.
    """
    return timedelta(minutes=conf.MARKET_FINAL_BUFFER_MINUTES)
