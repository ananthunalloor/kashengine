"""Tests for the company tasks."""

from apps.companies import tasks


def test_refresh_task_does_nothing_when_screener_is_off(monkeypatch):
    monkeypatch.setattr(tasks, "refresh_stale", lambda **kwargs: pytest_fail())

    assert tasks.refresh_stale_companies() == {"disabled": True}


def test_refresh_task_runs_when_screener_is_on(monkeypatch, settings):
    settings.SCREENER_ENABLED = True
    monkeypatch.setattr(tasks, "refresh_stale", lambda limit=None: {"refreshed": 2})

    assert tasks.refresh_stale_companies() == {"refreshed": 2}


def pytest_fail():
    raise AssertionError("refresh_stale must not run when SCREENER_ENABLED is false.")
