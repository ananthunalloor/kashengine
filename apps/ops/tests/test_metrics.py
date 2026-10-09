"""The numbers on the metrics page."""

from datetime import timedelta

import pytest
import redis
from django.utils import timezone

from apps.ops import metrics
from apps.ops.models import TaskRun

pytestmark = pytest.mark.django_db


def make(task_id, label, status, duration=None, **fields):
    return TaskRun.objects.create(
        task_id=task_id, task_name=label, label=label, status=status, duration_ms=duration, **fields
    )


def test_task_stats_count_runs_and_success_rate():
    make("1", "a", "success", 100)
    make("2", "a", "success", 300)
    make("3", "a", "failure", 200)
    make("4", "a", "pending")
    old = make("5", "b", "success", 50)
    TaskRun.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))

    [row] = metrics.task_stats(days=7)

    assert row["label"] == "a"
    assert row["runs"] == 4
    assert row["ok"] == 2
    assert row["failed"] == 1
    assert row["success_rate"] == 67
    assert row["avg_ms"] == 200
    assert row["max_ms"] == 300


def test_success_rate_is_empty_before_any_run_ends():
    make("1", "a", "pending")

    assert metrics.task_stats()[0]["success_rate"] is None


def test_daily_counts_give_zero_for_quiet_days():
    make("1", "a", "success")
    make("2", "a", "success")

    counts = metrics.daily_counts(TaskRun.objects.all(), "created_at", days=7)

    assert len(counts) == 7
    assert counts[-1] == 2
    assert sum(counts[:-1]) == 0


def test_the_charts_have_matching_lengths():
    for chart in metrics.charts(days=5):
        assert len(chart["labels"]) == len(chart["values"]) == 5
        if "alerts" in chart:
            assert len(chart["alerts"]) == 5


def test_table_counts_name_every_table():
    names = [name for name, _count in metrics.table_counts()]

    assert "Task runs" in names
    assert "Login events" in names


def test_host_stats_have_the_basics():
    stats = metrics.host_stats()

    assert stats["disk_total"] > 0
    assert stats["python"]
    assert stats["process_uptime_seconds"] >= 0


def test_redis_stats_is_none_when_redis_is_down(monkeypatch):
    def broken(*_args, **_kwargs):
        msg = "down"
        raise redis.ConnectionError(msg)

    monkeypatch.setattr(metrics.redis.Redis, "from_url", broken)

    assert metrics.redis_stats() is None


def test_worker_stats_is_none_when_the_broker_is_down(monkeypatch):
    from kombu.exceptions import OperationalError  # noqa: PLC0415

    from config.celery import app  # noqa: PLC0415

    class Broken:
        def active(self):
            raise OperationalError

    monkeypatch.setattr(app.control, "inspect", lambda **_kw: Broken())

    assert metrics.worker_stats() is None


def test_worker_stats(monkeypatch):
    from config.celery import app  # noqa: PLC0415

    class Fake:
        def active(self):
            return {"w1": [1, 2]}

        def reserved(self):
            return {"w1": [3], "w2": []}

    monkeypatch.setattr(app.control, "inspect", lambda **_kw: Fake())

    assert metrics.worker_stats() == [
        {"name": "w1", "active": 2, "reserved": 1},
        {"name": "w2", "active": 0, "reserved": 0},
    ]


@pytest.mark.parametrize(
    ("value", "text"), [(None, "–"), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024**2, "5.0 MB")]
)
def test_format_bytes(value, text):
    assert metrics.format_bytes(value) == text
