"""The health checks."""

from collections import namedtuple
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.news.models import NewsArticle
from apps.ops import health, schedule
from apps.ops.models import TaskRun

pytestmark = pytest.mark.django_db

Usage = namedtuple("Usage", "total used free")


def test_the_worst_status_wins():
    assert health.worst([health.OK, health.WARN, health.SKIP]) == health.WARN
    assert health.worst([health.OK, health.FAIL, health.WARN]) == health.FAIL
    assert health.worst([]) == health.SKIP


def test_an_error_in_a_check_is_a_failed_check_and_the_others_still_run():
    def broken():
        msg = "cannot connect"
        raise RuntimeError(msg)

    result = health.run_check(health.CheckSpec("x", "Thing X", broken))

    assert result.status == health.FAIL
    assert result.name == "Thing X"
    assert "cannot connect" in result.detail


def test_all_checks_run_when_services_are_down(monkeypatch):
    """No Redis, no worker, no LLM server: the page still gets an answer for every check."""
    monkeypatch.setattr(health, "_redis_client", lambda: SimpleNamespace(ping=_raise))
    monkeypatch.setattr(health, "check_workers", _raise)
    monkeypatch.setattr(health, "check_llm", _raise)
    specs = [
        health.CheckSpec(spec.key, spec.name, getattr(health, _name(spec)))
        for _group, specs in health.GROUPS
        for spec in specs
    ]

    results = [health.run_check(spec) for spec in specs]

    by_key = {r.key: r for r in results}
    assert len(results) == sum(len(specs) for _g, specs in health.GROUPS)
    assert by_key["redis"].status == health.FAIL
    assert by_key["workers"].status == health.FAIL
    assert by_key["llm"].status == health.FAIL
    assert by_key["database"].status == health.OK


def _name(spec):
    return spec.run.__name__


def _raise(*_args, **_kwargs):
    msg = "service is down"
    raise ConnectionError(msg)


def test_the_result_is_cached_for_a_short_time(monkeypatch):
    calls = []
    spec = health.CheckSpec("x", "X", lambda: calls.append(1) or health.Check("x", "X", "ok", ""))
    monkeypatch.setattr(health, "GROUPS", (("G", (spec,)),))

    health.run_all()
    health.run_all()
    assert len(calls) == 1

    health.run_all(use_cache=False)
    assert len(calls) == 2


def test_redis_check(monkeypatch):
    client = SimpleNamespace(
        ping=lambda: True, info=lambda: {"used_memory_human": "2M", "connected_clients": 3}
    )
    monkeypatch.setattr(health, "_redis_client", lambda: client)

    check = health.check_redis()

    assert check.status == health.OK
    assert "2M used, 3 clients" in check.detail


def test_workers_check(monkeypatch):
    from config.celery import app  # noqa: PLC0415

    monkeypatch.setattr(
        app.control, "inspect", lambda **_kw: SimpleNamespace(ping=lambda: {"w1@host": {}})
    )
    assert health.check_workers().status == health.OK

    monkeypatch.setattr(app.control, "inspect", lambda **_kw: SimpleNamespace(ping=lambda: None))
    assert health.check_workers().status == health.FAIL


@pytest.mark.parametrize(
    ("percent_used", "expected"), [(50, health.OK), (85, health.WARN), (95, health.FAIL)]
)
def test_disk_check(monkeypatch, percent_used, expected):
    monkeypatch.setattr(
        health.shutil, "disk_usage", lambda _p: Usage(100 * 1024**3, percent_used * 1024**3, 1)
    )
    assert health.check_disk().status == expected


@pytest.mark.parametrize(
    ("available_pct", "expected"), [(50, health.OK), (8, health.WARN), (3, health.FAIL)]
)
def test_memory_check(monkeypatch, available_pct, expected):
    total = 1000 * 1024
    monkeypatch.setattr(
        health,
        "read_meminfo",
        lambda: {"MemTotal": total, "MemAvailable": total * available_pct // 100},
    )
    assert health.check_memory().status == expected


def test_memory_check_without_proc(monkeypatch):
    monkeypatch.setattr(health, "read_meminfo", dict)
    assert health.check_memory().status == health.SKIP


def test_task_failure_check():
    assert health.check_task_failures().status == health.OK

    for n in range(2):
        TaskRun.objects.create(task_id=f"f{n}", task_name="a", label="a", status="failure")
    assert health.check_task_failures().status == health.WARN

    for n in range(2, 6):
        TaskRun.objects.create(task_id=f"f{n}", task_name="a", label="a", status="failure")
    assert health.check_task_failures().status == health.FAIL


def test_news_check_follows_the_age_of_the_newest_article():
    assert health.check_news_fresh().status == health.SKIP

    article = NewsArticle.objects.create(source="s", title="t", url="https://example.com/1")
    assert health.check_news_fresh().status == health.OK

    for hours, expected in ((10, health.WARN), (30, health.FAIL)):
        NewsArticle.objects.filter(pk=article.pk).update(
            fetched_at=timezone.now() - timedelta(hours=hours)
        )
        assert health.check_news_fresh().status == expected


def test_scoring_backlog_check(settings):
    settings.SENTIMENT_BATCH_SIZE = 2
    old = timezone.now() - timedelta(hours=10)
    for n in range(3):
        article = NewsArticle.objects.create(source="s", title="t", url=f"https://example.com/{n}")
        NewsArticle.objects.filter(pk=article.pk).update(fetched_at=old)

    check = health.check_scoring_backlog()

    assert check.status == health.WARN
    assert "3 articles" in check.summary


def test_telegram_check_does_not_need_the_network(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    assert health.check_telegram().status == health.WARN


def test_beat_check_without_history_is_skipped():
    assert health.check_beat().status == health.SKIP


def test_beat_check_finds_a_late_task():
    entry = schedule.entries()[0]
    TaskRun.objects.create(
        task_id="auto-1",
        task_name=entry.task,
        label=entry.task,
        status=TaskRun.Status.SUCCESS,
        started_at=timezone.now() - timedelta(days=3),
    )

    check = health.check_beat()

    assert check.status == health.WARN
    assert entry.task in check.detail


def test_beat_check_ignores_manual_runs():
    entry = schedule.entries()[0]
    TaskRun.objects.create(
        task_id="manual-1",
        task_name=entry.task,
        label=entry.task,
        trigger=TaskRun.Trigger.MANUAL,
        started_at=timezone.now() - timedelta(days=3),
    )

    assert health.check_beat().status == health.SKIP


def test_database_and_migration_checks():
    assert health.check_database().status == health.OK
    assert health.check_migrations().status == health.OK
