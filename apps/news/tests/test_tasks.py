"""Tests for the Celery tasks and the schedule."""

from django.conf import settings

from apps.news import tasks
from config.celery import app


def test_tasks_are_registered_and_every_scheduled_task_exists():
    assert "news.fetch_feeds" in app.tasks
    assert "news.scrape_articles" in app.tasks
    assert "companies.refresh_stale" in app.tasks
    assert "companies.link_news" in app.tasks
    for entry in settings.CELERY_BEAT_SCHEDULE.values():
        assert entry["task"] in app.tasks


def test_fetch_feeds_starts_the_scrape_and_the_company_link_when_there_are_new_articles(
    monkeypatch,
):
    started = []
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 3, "failed": {}})
    monkeypatch.setattr(tasks.scrape_articles, "delay", lambda: started.append("scrape"))
    monkeypatch.setattr(tasks.link_news, "delay", lambda: started.append("link"))

    assert tasks.fetch_feeds() == {"new": 3, "failed": {}}
    assert sorted(started) == ["link", "scrape"]


def test_fetch_feeds_does_nothing_more_when_there_is_nothing_new(monkeypatch):
    started = []
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 0, "failed": {}})
    monkeypatch.setattr(tasks.scrape_articles, "delay", lambda: started.append("scrape"))
    monkeypatch.setattr(tasks.link_news, "delay", lambda: started.append("link"))

    tasks.fetch_feeds()

    assert started == []


def test_fetch_feeds_can_skip_the_scrape(monkeypatch, settings):
    settings.NEWS_SCRAPE_FULL_TEXT = False
    started = []
    monkeypatch.setattr(tasks, "fetch_all_feeds", lambda: {"new": 1, "failed": {}})
    monkeypatch.setattr(tasks.scrape_articles, "delay", lambda: started.append("scrape"))
    monkeypatch.setattr(tasks.link_news, "delay", lambda: started.append("link"))

    tasks.fetch_feeds()

    assert started == ["link"]
