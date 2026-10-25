"""Trading days and times for the Indian market. All dates use the time zone of the settings.

Staff-maintained NSE cash/equity exceptions override the normal weekday session.
Unlisted weekdays are assumed to be regular sessions.

The functions are small helpers. `prediction.py`, `evaluation.py`, the report builder, the
delivery task and the Ops health checks all use them. The close time and the wait after the close
come from the site settings `MARKET_CLOSE_TIME` and `MARKET_FINAL_BUFFER_MINUTES`.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.siteconfig import conf
from apps.siteconfig.registry import clean_clock

from .models import TradingCalendarDay

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
    """Return whether the NSE equity calendar has a session on this date.

    Args:
        day: The date to test.

    Returns:
        Saved holidays close weekdays; special sessions can open weekends.
    """
    exception = TradingCalendarDay.objects.filter(day=day).first()
    if exception is not None:
        return exception.kind == TradingCalendarDay.Kind.SPECIAL
    return day.weekday() < FIRST_WEEKEND_WEEKDAY  # Monday to Friday.


def next_trading_day(day: date) -> date:
    """Return the day itself if it is a trading day. If not, return the next one.

    Args:
        day: The start date.

    Returns:
        A date that is the same as `day` or later, skipping saved holidays and weekends.
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
        The nearest earlier session, including special weekend sessions.
    """
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def session_close(day: date) -> datetime:
    """Return the close time of the market on a day.

    A special session uses its saved close. Otherwise the time comes from the site setting
    `MARKET_CLOSE_TIME` (format HH:MM, in IST).

    Args:
        day: The date of the session.

    Returns:
        A timezone-aware datetime on `day` at the close time, in the market time zone.

    Raises:
        ValueError: If the saved special session has no closing time.
    """
    exception = TradingCalendarDay.objects.filter(
        day=day, kind=TradingCalendarDay.Kind.SPECIAL
    ).first()
    close = exception.closes_at if exception else clean_clock(conf.MARKET_CLOSE_TIME)
    if close is None:
        raise ValueError(f"Special session on {day} has no closing time.")
    return datetime.combine(day, close, tzinfo=market_tz())


def session_open(day: date) -> datetime:
    """Return the opening time of the market on a day.

    A special session uses its saved opening. Otherwise the opening is 09:15 IST.

    Args:
        day: The date of the session.

    Returns:
        A timezone-aware datetime on `day` at the opening time, in the market time zone.

    Raises:
        ValueError: If the saved special session has no opening time.
    """
    exception = TradingCalendarDay.objects.filter(
        day=day, kind=TradingCalendarDay.Kind.SPECIAL
    ).first()
    opening = exception.opens_at if exception else time(9, 15)
    if opening is None:
        raise ValueError(f"Special session on {day} has no opening time.")
    return datetime.combine(day, opening, tzinfo=market_tz())


def final_buffer() -> timedelta:
    """Return how long after the close Yahoo needs to show the final price.

    The value comes from the site setting `MARKET_FINAL_BUFFER_MINUTES`.

    Returns:
        A `timedelta` in minutes. `evaluation.py` adds it to the close time to find when a
        quote is final.
    """
    return timedelta(minutes=conf.MARKET_FINAL_BUFFER_MINUTES)


def latest_completed_day(now: datetime | None = None) -> date:
    """Return the latest trading day whose close and final-data buffer have passed.

    Args:
        now: The time to test. The default is the current time.

    Returns:
        Today if today is a trading day and the close plus `final_buffer()` has passed. Else the
        trading day before today.
    """
    now = now or timezone.now()
    today = today_ist(now)
    if is_trading_day(today) and now >= session_close(today) + final_buffer():
        return today
    return previous_trading_day(today)
