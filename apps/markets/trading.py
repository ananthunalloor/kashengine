"""Trading days and times for the Indian market. All dates use the time zone of the settings.

We have no list of market holidays. A holiday counts as a trading day here. A prediction for a
holiday ends as "void" (see evaluation.py).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.siteconfig import conf
from apps.siteconfig.registry import clean_clock

FIRST_WEEKEND_WEEKDAY = 5  # datetime.weekday(): Monday is 0, Saturday is 5.


def market_tz() -> ZoneInfo:
    """Return the time zone of the market (TIME_ZONE in the settings)."""
    return ZoneInfo(settings.TIME_ZONE)


def today_ist(now: datetime | None = None) -> date:
    """Return the date in the market time zone. The default time is now."""
    return (now or timezone.now()).astimezone(market_tz()).date()


def is_trading_day(day: date) -> bool:
    """Return True for a weekday. Market holidays are not known."""
    return day.weekday() < FIRST_WEEKEND_WEEKDAY  # Monday to Friday.


def next_trading_day(day: date) -> date:
    """Return the day itself if it is a trading day. If not, return the next one."""
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def previous_trading_day(day: date) -> date:
    """Return the last trading day before this day."""
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def session_close(day: date) -> datetime:
    """Return the close time of the market on a day."""
    close = clean_clock(conf.MARKET_CLOSE_TIME)
    return datetime.combine(day, close, tzinfo=market_tz())


def final_buffer() -> timedelta:
    """How long after the close Yahoo needs to show the final price."""
    return timedelta(minutes=conf.MARKET_FINAL_BUFFER_MINUTES)
