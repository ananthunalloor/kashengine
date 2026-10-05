"""Trading days and times for the Indian market. All dates use the time zone of the settings (IST).

We have no list of market holidays. A holiday counts as a trading day here. A prediction for a
holiday ends as "void" (see evaluation.py).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

MARKET_CLOSE = time(15, 30)
# After the close, Yahoo needs a few minutes to show the final price.
FINAL_BUFFER = timedelta(minutes=10)


def market_tz() -> ZoneInfo:
    return ZoneInfo(settings.TIME_ZONE)


def today_ist(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(market_tz()).date()


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5  # Monday to Friday.


def next_trading_day(day: date) -> date:
    """The day itself if it is a trading day. If not, the next one."""
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def previous_trading_day(day: date) -> date:
    """The last trading day before this day."""
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def session_close(day: date) -> datetime:
    return datetime.combine(day, MARKET_CLOSE, tzinfo=market_tz())
