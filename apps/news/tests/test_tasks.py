"""Tests for the Celery tasks and the schedule."""

import pytest
from django_celery_beat.models import PeriodicTask

from apps.delivery import tasks as delivery_tasks  # noqa: F401  # Import registers the tasks.
from apps.ipos import tasks as ipo_tasks  # noqa: F401  # Import registers the tasks.
from apps.markets import tasks as market_tasks  # noqa: F401  # Import registers the tasks.
from apps.news import tasks
from config.celery import app


@pytest.mark.django_db
def test_tasks_are_registered_and_every_scheduled_task_exists():
    for name in (
        "news.fetch_feeds",
        "news.scrape_articles",
        "news.score_articles",
        "companies.refresh_stale",
        "companies.link_news",
        "markets.fetch_quotes",
        "markets.predict",
        "ipos.collect",
        "ipos.refresh_metrics",
        "ipos.score",
        "delivery.send_daily_report",
    ):
        assert name in app.tasks
    # The first migration saved the schedule in the database.
    scheduled = PeriodicTask.objects.filter(crontab__isnull=False)
    assert scheduled.count() >= 13
    for entry in scheduled.exclude(task__startswith="celery."):
        assert entry.task in app.tasks


def record(monkeypatch, started: list) -> None:
    monkeypatch.setattr(tasks.scrape_articles, "delay", lambda: started.append("scrape"))
    monkeypatch.setattr(tasks.score_articles, "delay", lambda: started.append("score"))
    monkeypatch.setattr(tasks.link_news, "delay", lambda: started.append("link"))


def test_new_articles_start_the_company_link_and_the_scrape(monkeypatch):
    started = []
    record(monkeypatch, started)
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 3, "failed": {}})

    assert tasks.fetch_feeds() == {"new": 3, "failed": {}}
    # The scoring does not start here. The scrape task starts it when it is done.
    assert sorted(started) == ["link", "scrape"]


def test_without_the_scrape_the_scoring_starts_at_once(monkeypatch, settings):
    settings.NEWS_SCRAPE_FULL_TEXT = False
    started = []
    record(monkeypatch, started)
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 1, "failed": {}})

    tasks.fetch_feeds()

    assert sorted(started) == ["link", "score"]


def test_nothing_new_starts_nothing(monkeypatch):
    started = []
    record(monkeypatch, started)
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 0, "failed": {}})

    tasks.fetch_feeds()

    assert started == []


def test_the_scrape_task_starts_the_scoring_when_it_is_done(monkeypatch):
    started = []
    record(monkeypatch, started)
    monkeypatch.setattr(tasks, "scrape_pending", lambda limit=None: {"scraped": 2})

    assert tasks.scrape_articles() == {"scraped": 2}
    assert started == ["score"]


def test_the_score_task_runs_the_scoring(monkeypatch):
    calls = []

    def fake_score_pending(limit=None):
        calls.append(limit)
        return {"scored": 4, "failed": 0, "stopped": False}

    monkeypatch.setattr(tasks, "score_pending", fake_score_pending)

    assert tasks.score_articles(limit=10)["scored"] == 4
    assert calls == [10]
