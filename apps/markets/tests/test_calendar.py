from datetime import UTC, date, datetime, time

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.markets import tasks
from apps.markets.calendar import calendar_snapshot
from apps.markets.models import Prediction, TradingCalendarDay
from apps.markets.trading import (
    is_trading_day,
    market_tz,
    next_trading_day,
    previous_trading_day,
    session_close,
    session_open,
)

from .helpers import MON, PREV_FRI, SAT, SUN, TUE, ist

pytestmark = pytest.mark.django_db


def holiday(day=MON):
    return TradingCalendarDay.objects.create(day=day, kind="holiday", reason="Exchange holiday")


def special(day=SAT):
    return TradingCalendarDay.objects.create(
        day=day,
        kind="special",
        reason="Exchange-announced special session",
        opens_at=time(18),
        closes_at=time(19),
        source_url="https://www.nseindia.com/",
    )


def test_holidays_and_special_weekends_drive_shared_trading_helpers():
    holiday()
    special()
    assert not is_trading_day(MON)
    assert is_trading_day(SAT)
    assert next_trading_day(MON) == TUE
    assert previous_trading_day(TUE) == PREV_FRI
    assert next_trading_day(SAT) == SAT
    assert session_open(SAT) == ist(SAT, 18)
    assert session_close(SAT) == ist(SAT, 19)


@pytest.mark.parametrize(
    ("hour", "minute", "is_open", "boundary"),
    [
        (9, 14, False, (9, 15)),
        (9, 15, True, (15, 30)),
        (15, 29, True, (15, 30)),
        (15, 30, False, (0, 0)),
    ],
)
def test_regular_session_boundaries(hour, minute, is_open, boundary):
    snapshot = calendar_snapshot(MON.year, ist(MON, hour, minute))
    assert snapshot["is_open"] is is_open
    local_boundary = snapshot["next_change_at"].astimezone(market_tz())
    assert (local_boundary.hour, local_boundary.minute) == boundary
    assert snapshot["next_change_at"] > snapshot["as_of"]


def test_holiday_reason_and_special_session_hours():
    holiday()
    special()
    closed = calendar_snapshot(MON.year, ist(MON, 10))
    assert not closed["is_open"]
    assert closed["reason"] == "Exchange holiday"
    assert [row["day"] for row in closed["days"]] == [MON, SAT]
    assert closed["days"][1]["opens_at"] == "18:00"
    assert not calendar_snapshot(SAT.year, ist(SAT, 17))["is_open"]
    assert calendar_snapshot(SAT.year, ist(SAT, 18))["is_open"]
    assert not calendar_snapshot(SAT.year, ist(SAT, 19))["is_open"]
    assert calendar_snapshot(SAT.year, ist(SAT, 18))["special_reason"] == (
        "Exchange-announced special session"
    )


def test_weekend_and_utc_date_use_ist():
    assert calendar_snapshot(SUN.year, ist(SUN, 10))["reason"] == "Weekend"
    stamp = datetime(2026, 10, 4, 20, 0, tzinfo=UTC)
    snapshot = calendar_snapshot(2026, stamp)
    assert snapshot["as_of"].astimezone(market_tz()).date() == MON
    assert snapshot["next_change_at"] == ist(MON, 9, 15)


def test_year_filter_includes_only_requested_year():
    holiday()
    holiday(date(2027, 1, 1))
    assert len(calendar_snapshot(2026, ist(MON, 10))["days"]) == 1
    assert len(calendar_snapshot(2027, ist(MON, 10))["days"]) == 1
    assert calendar_snapshot(2028, ist(MON, 10))["days"] == []


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "holiday", "reason": " "},
        {"kind": "holiday", "reason": "Holiday", "opens_at": time(9)},
        {"kind": "special", "reason": "Special"},
        {"kind": "special", "reason": "Special", "opens_at": time(19), "closes_at": time(18)},
    ],
)
def test_invalid_calendar_entries_are_rejected_by_staff_forms(values):
    with pytest.raises(ValidationError):
        TradingCalendarDay(day=MON, **values).full_clean()


def test_database_enforces_unique_dates_and_session_hours():
    holiday()
    with pytest.raises(IntegrityError), transaction.atomic():
        holiday()
    with pytest.raises(IntegrityError), transaction.atomic():
        TradingCalendarDay.objects.create(day=SAT, kind="special", reason="Missing times")


def test_prediction_task_skips_saved_holidays_and_runs_special_weekends(monkeypatch):
    holiday()
    special()
    monkeypatch.setattr(tasks, "today_ist", lambda: MON)
    monkeypatch.setattr(tasks, "make_prediction", lambda: pytest.fail("Holiday prediction"))
    assert "skipped" in tasks.predict()
    monkeypatch.setattr(tasks, "today_ist", lambda: SAT)
    called = []

    def predict():
        called.append(True)
        return Prediction(target_date=SAT, direction="flat", confidence=0), True

    monkeypatch.setattr(tasks, "make_prediction", predict)
    assert tasks.predict()["target_date"] == SAT.isoformat()
    assert called == [True]
