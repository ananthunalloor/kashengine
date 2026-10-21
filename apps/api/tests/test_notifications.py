"""Staff task notifications use a reconnectable SSE cursor."""

import json
import re

import pytest
from django.test import Client
from django.utils import timezone

from apps.ops.models import TaskRun

pytestmark = pytest.mark.django_db


def test_notifications_require_staff(member, django_user_model):
    member_client = Client()
    member_client.force_login(member)
    response = member_client.get("/api/app/notifications/")

    assert response.status_code == 204


def test_notifications_require_a_session():
    response = Client().get("/api/app/notifications/")

    assert response.status_code == 401


def test_notifications_send_only_finished_runs_after_the_cursor(django_user_model):
    staff = django_user_model.objects.create_user("staff", is_staff=True)
    staff_client = Client()
    staff_client.force_login(staff)
    old_run = TaskRun.objects.create(
        task_id="old-run",
        task_name="jobs.old",
        label="Old job",
        status=TaskRun.Status.SUCCESS,
        finished_at=timezone.now(),
    )
    cursor_time = timezone.now()
    finished = TaskRun.objects.create(
        task_id="finished-run",
        task_name="jobs.failed",
        label="Failed job",
        status=TaskRun.Status.FAILURE,
        error="ValueError: source unavailable\ntraceback details",
        finished_at=cursor_time,
    )

    response = staff_client.get(
        "/api/app/notifications/",
        headers={"Last-Event-ID": f"{old_run.finished_at.isoformat()}|{old_run.pk}"},
    )
    content = response.content.decode()
    event = re.search(r"data: (.+)", content)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert "no-store" in response["Cache-Control"]
    assert event is not None
    payload = json.loads(event.group(1))
    assert payload == {
        "run_id": finished.pk,
        "label": "Failed job",
        "status": TaskRun.Status.FAILURE,
        "error": "ValueError: source unavailable",
        "url": f"/ops/runs/{finished.pk}/",
    }
    assert f"id: {finished.finished_at.isoformat()}|{finished.pk}" in content
