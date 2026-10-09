"""The jobs that an admin can start."""

from datetime import timedelta

import pytest
from django.core.management import get_commands
from django.urls import reverse
from django.utils import timezone

from apps.ops import jobs, schedule
from apps.ops.models import AuditEvent, TaskRun

pytestmark = pytest.mark.django_db


def job(key):
    return jobs.JOBS_BY_KEY[key]


def test_every_job_has_a_unique_key_and_a_unique_run_label():
    assert len({j.key for j in jobs.JOBS}) == len(jobs.JOBS)
    assert len({j.run_label for j in jobs.JOBS}) == len(jobs.JOBS)


def test_every_command_job_names_a_real_command():
    known = set(get_commands())
    assert {j.target for j in jobs.JOBS if j.kind == jobs.COMMAND} <= known


def test_every_task_job_names_a_registered_task():
    from config.celery import app  # noqa: PLC0415

    app.loader.import_default_modules()
    registered = set(app.tasks)
    assert {j.target for j in jobs.JOBS if j.kind == jobs.TASK} <= registered
    assert jobs.RUN_COMMAND_TASK in registered


def test_every_scheduled_task_can_be_started_by_hand():
    targets = {j.target for j in jobs.JOBS if j.kind == jobs.TASK}
    assert {entry.task for entry in schedule.entries()} <= targets


def test_the_allow_list_has_the_fixed_arguments():
    assert ("predict_market", ("--force",)) in jobs.COMMAND_ALLOWLIST
    assert ("predict_market", ()) not in jobs.COMMAND_ALLOWLIST


def test_run_labels():
    assert job("news-fetch").run_label == "news.fetch_feeds"
    assert job("predict-force").run_label == "command: predict_market --force"
    assert job("predict-force").task_name == "ops.run_command"


def test_a_task_job_is_queued_with_a_pending_row(boss, queue):
    run = jobs.start_job(job("news-fetch"), boss)

    assert queue == [("news.fetch_feeds", [], run.task_id)]
    assert run.status == TaskRun.Status.PENDING
    assert run.trigger == TaskRun.Trigger.MANUAL
    assert run.triggered_by == boss
    assert AuditEvent.objects.filter(actor=boss, action="run job").count() == 1


def test_a_command_job_runs_in_the_command_task(boss, queue):
    run = jobs.start_job(job("predict-force"), boss)

    assert queue == [("ops.run_command", ["predict_market", ["--force"]], run.task_id)]
    assert run.label == "command: predict_market --force"
    assert run.args == "--force"


def test_the_same_job_cannot_start_twice(boss, queue):
    jobs.start_job(job("news-fetch"), boss)

    with pytest.raises(jobs.JobBusyError):
        jobs.start_job(job("news-fetch"), boss)

    assert len(queue) == 1


def test_an_old_active_run_does_not_block(boss, queue):
    old = jobs.start_job(job("news-fetch"), boss)
    TaskRun.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=1))

    jobs.start_job(job("news-fetch"), boss)

    assert len(queue) == 2


def test_a_job_that_is_done_does_not_block(boss, queue):
    first = jobs.start_job(job("news-fetch"), boss)
    TaskRun.objects.filter(pk=first.pk).update(status=TaskRun.Status.SUCCESS)

    jobs.start_job(job("news-fetch"), boss)

    assert len(queue) == 2


def test_a_dispatch_error_marks_the_run_as_failed(boss, monkeypatch):
    def broken(*_args):
        msg = "redis is down"
        raise ConnectionError(msg)

    monkeypatch.setattr(jobs, "dispatch", broken)

    with pytest.raises(jobs.JobDispatchError):
        jobs.start_job(job("news-fetch"), boss)

    run = TaskRun.objects.get()
    assert run.status == TaskRun.Status.FAILURE
    assert "redis is down" in run.error
    assert jobs.active_run(job("news-fetch")) is None


# The Jobs page


def run_url(key):
    return reverse("ops:job_run", args=[key])


def test_a_superuser_starts_a_job(boss_client, queue):
    response = boss_client.post(run_url("news-fetch"))

    run = TaskRun.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("ops:run", args=[run.pk])
    assert len(queue) == 1


def test_a_staff_user_cannot_start_a_job(staff_client, queue):
    assert staff_client.post(run_url("news-fetch")).status_code == 403
    assert queue == []
    assert not TaskRun.objects.exists()


def test_a_normal_user_cannot_start_a_job(member_client, queue):
    assert member_client.post(run_url("news-fetch")).status_code == 403
    assert queue == []


def test_an_anonymous_user_is_sent_to_the_login(client, queue):
    response = client.post(run_url("news-fetch"))

    assert response.status_code == 302
    assert "/login/" in response.url
    assert queue == []


def test_a_job_does_not_start_with_a_get_request(boss_client, queue):
    assert boss_client.get(run_url("news-fetch")).status_code == 405
    assert queue == []


def test_an_unknown_job_is_a_404(boss_client, queue):
    assert boss_client.post(run_url("rm-rf")).status_code == 404


def test_a_job_with_a_warning_needs_the_confirmation(boss_client, queue):
    response = boss_client.post(run_url("report-send"))

    assert response.status_code == 302
    assert response.url == reverse("ops:jobs")
    assert queue == []

    boss_client.post(run_url("report-send"), {"confirm": "yes"})

    assert [name for name, _args, _id in queue] == ["delivery.send_daily_report"]


def test_a_busy_job_shows_a_message_and_does_not_start_again(boss_client, queue):
    boss_client.post(run_url("news-fetch"))

    response = boss_client.post(run_url("news-fetch"), follow=True)

    assert len(queue) == 1
    assert "already waiting or running" in response.content.decode()


def test_a_queue_error_shows_a_message(boss_client, monkeypatch):
    def broken(*_args):
        raise ConnectionError

    monkeypatch.setattr(jobs, "dispatch", broken)

    response = boss_client.post(run_url("news-fetch"), follow=True)

    assert "could not be queued" in response.content.decode()
