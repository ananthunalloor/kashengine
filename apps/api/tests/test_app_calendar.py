from datetime import date, time

import pytest

from apps.api.models import LiveEvent
from apps.markets.models import TradingCalendarDay

pytestmark = pytest.mark.django_db
URL = "/api/app/calendar"


def test_requires_session_and_valid_year(client, member):
    assert client.get(URL, {"year": 2026}).status_code == 401
    client.force_login(member)
    for params in ({}, {"year": 1999}, {"year": 2101}, {"year": "invalid"}):
        assert client.get(URL, params).status_code == 422


def test_yearly_entries_reasons_and_session_snapshot(client, member):
    TradingCalendarDay.objects.create(day=date(2026, 1, 26), kind="holiday", reason="Republic Day")
    TradingCalendarDay.objects.create(
        day=date(2026, 11, 8),
        kind="special",
        reason="Example special session",
        opens_at=time(18),
        closes_at=time(19),
    )
    client.force_login(member)
    response = client.get(URL, {"year": 2026})
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    body = response.json()
    assert body["as_of"].endswith("Z")
    assert body["next_change_at"].endswith("Z")
    assert [row["reason"] for row in body["days"]] == ["Republic Day", "Example special session"]
    assert body["days"][1]["closes_at"] == "19:00"
    assert body["year"] == 2026
    assert client.get("/api/app/session").json()["market_calendar"]["year"] >= 2026
    assert client.get(URL, {"year": 2027}).json()["days"] == []
    assert client.post(URL, {"year": 2026}).status_code == 405


def test_calendar_available_even_with_expired_subscription(client, member, expire, settings):
    settings.SUBSCRIPTIONS_REQUIRED = True
    expire(member)
    client.force_login(member)
    assert client.get(URL, {"year": 2026}).status_code == 200


def test_calendar_changes_invalidate_session_after_commit(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        row = TradingCalendarDay.objects.create(
            day=date(2026, 1, 26), kind="holiday", reason="Republic Day"
        )
    assert LiveEvent.objects.filter(scope="session").exists()
    LiveEvent.objects.all().delete()
    with django_capture_on_commit_callbacks(execute=True):
        row.delete()
    assert LiveEvent.objects.filter(scope="session").exists()
