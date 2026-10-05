"""Tests for the trading day helpers."""

from datetime import UTC, datetime

from apps.markets.trading import (
    is_trading_day,
    market_tz,
    next_trading_day,
    previous_trading_day,
    session_close,
    today_ist,
)

from .helpers import FRI, MON, NEXT_MON, SAT, SUN, TUE, ist


def test_weekdays_are_trading_days_and_the_weekend_is_not():
    assert [is_trading_day(d) for d in (MON, FRI, SAT, SUN)] == [True, True, False, False]


def test_next_trading_day_keeps_a_trading_day_and_skips_the_weekend():
    assert next_trading_day(MON) == MON
    assert next_trading_day(SAT) == NEXT_MON
    assert next_trading_day(SUN) == NEXT_MON


def test_previous_trading_day_skips_the_weekend():
    assert previous_trading_day(TUE) == MON
    assert previous_trading_day(NEXT_MON) == FRI
    assert previous_trading_day(SUN) == FRI


def test_session_close_is_15_30_in_india():
    close = session_close(MON)
    assert close == ist(MON, 15, 30)
    assert close.astimezone(UTC).hour == 10  # 15:30 IST is 10:00 UTC.
    assert market_tz().key == "Asia/Kolkata"


def test_today_uses_the_india_date_not_the_utc_date():
    # 20:00 UTC on Sunday is 01:30 on Monday in India.
    now = datetime(2026, 10, 4, 20, 0, tzinfo=UTC)
    assert today_ist(now) == MON
