"""Task runs and logins are recorded by signals."""

import logging
from types import SimpleNamespace

import pytest
from celery import shared_task
from celery.signals import task_prerun
from django.test import Client

from apps.ops import signals
from apps.ops.models import LoginEvent, TaskRun

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


@shared_task(name="ops_tests.ok")
def ok_task():
    return {"answer": 42}


@shared_task(name="ops_tests.boom")
def failing_task():
    msg = "boom"
    raise ValueError(msg)


def test_a_finished_task_is_recorded():
    result = ok_task.apply()

    run = TaskRun.objects.get(task_id=result.id)
    assert run.status == TaskRun.Status.SUCCESS
    assert run.trigger == TaskRun.Trigger.AUTO
    assert run.label == "ops_tests.ok"
    assert "42" in run.result
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.duration_ms is not None


def test_a_failed_task_keeps_the_error():
    result = failing_task.apply()

    run = TaskRun.objects.get(task_id=result.id)
    assert run.status == TaskRun.Status.FAILURE
    assert "ValueError" in run.error
    assert "boom" in run.error


def test_a_manual_run_keeps_its_row_and_its_label():
    row = TaskRun.objects.create(
        task_id="manual-1",
        task_name="ops_tests.ok",
        label="command: llm_check",
        trigger=TaskRun.Trigger.MANUAL,
    )

    ok_task.apply(task_id="manual-1")

    row.refresh_from_db()
    assert row.status == TaskRun.Status.SUCCESS
    assert row.trigger == TaskRun.Trigger.MANUAL
    assert row.label == "command: llm_check"
    assert TaskRun.objects.count() == 1


def test_the_internal_celery_tasks_are_not_recorded():
    task = SimpleNamespace(name="celery.backend_cleanup", request=SimpleNamespace(hostname="w"))

    task_prerun.send(
        sender="celery.backend_cleanup", task_id="internal-1", task=task, args=(), kwargs={}
    )

    assert not TaskRun.objects.exists()


def test_a_recording_error_does_not_break_the_task(monkeypatch, caplog):
    def broken(*_args, **_kwargs):
        msg = "database is gone"
        raise RuntimeError(msg)

    monkeypatch.setattr(TaskRun.objects, "get_or_create", broken)
    task = SimpleNamespace(name="ops_tests.ok", request=SimpleNamespace(hostname="w"))

    with caplog.at_level(logging.ERROR, logger="apps.ops.signals"):
        signals.on_task_prerun(task_id="x", task=task, args=(), kwargs={})

    assert "Could not record the start" in caplog.text


def test_long_text_is_cut():
    assert signals.clip("a" * 50, 10) == "a" * 9 + "…"
    assert signals.clip("short", 10) == "short"


def test_a_login_is_recorded_with_the_address(member):
    client = Client()

    client.post(
        "/login/",
        {"username": "member", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1", "User-Agent": "TestBrowser/1.0"},
    )

    event = LoginEvent.objects.get(kind=LoginEvent.Kind.LOGIN, user=member)
    assert event.ip_address == "203.0.113.9"
    assert event.user_agent == "TestBrowser/1.0"
    assert event.session_key == client.session.session_key


def test_a_failed_login_never_saves_the_password(member):
    Client().post("/login/", {"username": "member", "password": "wrong-password-xyz"})

    event = LoginEvent.objects.get(kind=LoginEvent.Kind.FAILED)
    assert event.username == "member"
    assert event.user is None
    assert "wrong-password-xyz" not in " ".join(str(v) for v in vars(event).values())


def test_a_logout_is_recorded(member):
    client = Client()
    client.force_login(member)

    client.logout()

    assert LoginEvent.objects.filter(kind=LoginEvent.Kind.LOGOUT, user=member).count() == 1


def test_a_bad_forwarded_address_does_not_break_the_login(member):
    response = Client().post(
        "/login/",
        {"username": "member", "password": PASSWORD},
        headers={"X-Forwarded-For": "not-an-address"},
    )

    assert response.status_code == 302
    assert LoginEvent.objects.get(kind=LoginEvent.Kind.LOGIN).ip_address is None
