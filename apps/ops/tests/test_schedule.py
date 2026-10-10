"""Read and change the beat schedule (it is in the database)."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.ops import schedule

pytestmark = pytest.mark.django_db


def test_every_entry_has_a_cron_text():
    entries = schedule.entries()

    assert entries
    for entry in entries:
        assert len(entry.cron_text.split()) == 5


def test_the_prune_task_is_scheduled():
    assert [e.cron_text for e in schedule.entries_for("ops.prune")] == ["40 3 * * *"]


def test_next_run_is_in_the_future():
    now = datetime.now(UTC)

    upcoming = schedule.next_run("ops.prune", now)

    assert upcoming is not None
    assert now < upcoming <= now + timedelta(days=1, minutes=1)


def test_a_task_that_is_not_scheduled_has_no_next_run():
    now = datetime.now(UTC)

    assert schedule.next_run("no.such.task", now) is None
    assert schedule.overdue_by("no.such.task", now, now) is None


def test_overdue_by():
    now = datetime.now(UTC)

    assert schedule.overdue_by("ops.prune", now - timedelta(hours=1), now) is None
    late = schedule.overdue_by("ops.prune", now - timedelta(days=3), now)
    assert late is not None
    assert late > timedelta(days=1)
