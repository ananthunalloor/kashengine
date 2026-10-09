"""The tasks of the ops app."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.ops import tasks
from apps.ops.models import AuditEvent, LoginEvent, TaskRun

pytestmark = pytest.mark.django_db


def test_an_allowed_command_runs_and_its_output_is_saved(monkeypatch):
    def fake_call_command(name, *args, stdout, stderr, **_kw):
        stdout.write(f"ran {name} {' '.join(args)}\nsecond line\n")
        stderr.write("a warning\n")

    monkeypatch.setattr(tasks, "call_command", fake_call_command)
    TaskRun.objects.create(task_id="cmd-1", task_name="ops.run_command", label="command: x")

    result = tasks.run_command.apply(args=["predict_market", ["--force"]], task_id="cmd-1")

    assert result.get() == {"command": "predict_market", "lines": 2}
    run = TaskRun.objects.get(task_id="cmd-1")
    assert "ran predict_market --force" in run.output
    assert "[stderr]" in run.output
    assert "a warning" in run.output


def test_a_command_that_is_not_in_the_list_does_not_run(monkeypatch):
    called = []
    monkeypatch.setattr(tasks, "call_command", lambda *a, **k: called.append(a))

    result = tasks.run_command.apply(args=["flush", ["--noinput"]])

    assert result.failed()
    assert called == []


def test_a_listed_command_with_other_arguments_does_not_run(monkeypatch):
    called = []
    monkeypatch.setattr(tasks, "call_command", lambda *a, **k: called.append(a))

    result = tasks.run_command.apply(args=["predict_market", ["--force", "--other"]])

    assert result.failed()
    assert called == []


def test_the_output_is_saved_when_the_command_fails(monkeypatch):
    def failing(name, *args, stdout, **_kw):
        stdout.write("half done\n")
        msg = "stopped"
        raise RuntimeError(msg)

    monkeypatch.setattr(tasks, "call_command", failing)
    TaskRun.objects.create(task_id="cmd-2", task_name="ops.run_command", label="command: x")

    result = tasks.run_command.apply(args=["predict_market", ["--force"]], task_id="cmd-2")

    assert result.failed()
    run = TaskRun.objects.get(task_id="cmd-2")
    assert run.status == TaskRun.Status.FAILURE
    assert "half done" in run.output
    assert "stopped" in run.error


def make_run(task_id, status, **fields):
    return TaskRun.objects.create(
        task_id=task_id, task_name="x", label="x", status=status, **fields
    )


def age(model, pk, **fields):
    model.objects.filter(pk=pk).update(**fields)


def test_prune_deletes_old_history_and_keeps_new_history(boss):
    old = timezone.now() - timedelta(days=settings.OPS_RETENTION_DAYS + 1)
    old_run = make_run("old", TaskRun.Status.SUCCESS)
    new_run = make_run("new", TaskRun.Status.SUCCESS)
    age(TaskRun, old_run.pk, created_at=old)
    LoginEvent.objects.all().delete()
    old_event = LoginEvent.objects.create(kind=LoginEvent.Kind.LOGIN, username="a")
    age(LoginEvent, old_event.pk, created_at=old)
    LoginEvent.objects.create(kind=LoginEvent.Kind.LOGIN, username="b")

    result = tasks.prune()

    assert result["task_runs"] == 1
    assert result["login_events"] == 1
    assert list(TaskRun.objects.all()) == [new_run]
    assert LoginEvent.objects.filter(username="b").exists()


def test_prune_keeps_the_audit_trail_for_a_year(boss):
    year = timezone.now() - timedelta(days=366)
    recent = timezone.now() - timedelta(days=settings.OPS_RETENTION_DAYS + 30)
    gone = AuditEvent.objects.create(actor=boss, actor_name="boss", action="a")
    kept = AuditEvent.objects.create(actor=boss, actor_name="boss", action="b")
    age(AuditEvent, gone.pk, created_at=year)
    age(AuditEvent, kept.pk, created_at=recent)

    result = tasks.prune()

    assert result["audit_events"] == 1
    assert list(AuditEvent.objects.all()) == [kept]


def test_prune_marks_lost_runs_as_failed():
    now = timezone.now()
    pending = make_run("p", TaskRun.Status.PENDING)
    age(TaskRun, pending.pk, created_at=now - timedelta(hours=3))
    started = make_run("s", TaskRun.Status.STARTED, started_at=now - timedelta(hours=4))
    fresh = make_run("f", TaskRun.Status.STARTED, started_at=now - timedelta(minutes=5))

    result = tasks.prune()

    assert result["lost_pending"] == 1
    assert result["lost_started"] == 1
    for row in (pending, started):
        row.refresh_from_db()
        assert row.status == TaskRun.Status.FAILURE
        assert row.finished_at is not None
        assert row.error
    fresh.refresh_from_db()
    assert fresh.status == TaskRun.Status.STARTED


def test_prune_deletes_expired_sessions_only():
    Session.objects.create(
        session_key="old", session_data="x", expire_date=timezone.now() - timedelta(days=1)
    )
    Session.objects.create(
        session_key="live", session_data="x", expire_date=timezone.now() + timedelta(days=1)
    )

    result = tasks.prune()

    assert result["sessions"] == 1
    assert list(Session.objects.values_list("session_key", flat=True)) == ["live"]
