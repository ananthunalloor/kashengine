import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from apps.api import live
from apps.api.models import LiveEvent
from apps.ops.models import TaskRun
from apps.ops.tasks import prune

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def empty_live_history():
    LiveEvent.objects.all().delete()


def one_cycle(monkeypatch):
    times = iter([0, 0, 21])
    monkeypatch.setattr(
        live, "time", SimpleNamespace(monotonic=lambda: next(times), sleep=lambda _: None)
    )


def read_changes(response):
    try:
        chunks = b"".join(response.streaming_content).decode()
    finally:
        response.close()
    return [
        json.loads(block.split("data: ", 1)[1])
        for block in chunks.split("\n\n")
        if "event: change\n" in block
    ]


@pytest.mark.parametrize(
    ("path", "signed_in", "status"),
    [
        ("/api/app/events", False, 401),
        ("/api/app/ops/events", False, 401),
        ("/api/app/ops/events", True, 403),
    ],
)
def test_stream_auth_happens_before_event_reads(client, member, path, signed_in, status):
    if signed_in:
        client.force_login(member)
    with patch.object(LiveEvent.objects, "order_by", side_effect=AssertionError("Data read")):
        response = client.get(path)
    assert response.status_code == status
    assert response["Cache-Control"] == "private, no-store"
    assert "Location" not in response


def test_first_connection_starts_now_not_with_historical_popups(client, staff, monkeypatch):
    client.force_login(staff)
    LiveEvent.objects.create(scope="ops", staff_only=True, payload={"run": {"id": 1}})
    one_cycle(monkeypatch)
    response = client.get("/api/app/ops/events")
    assert response["Content-Type"] == "text/event-stream"
    assert response["X-Accel-Buffering"] == "no"
    assert response["Cache-Control"] == "private, no-store"
    assert read_changes(response) == []


def test_reconnect_replays_committed_events_without_secrets(client, staff, monkeypatch):
    client.force_login(staff)
    cursor = LiveEvent.objects.create(scope="news")
    LiveEvent.objects.create(
        scope="ops",
        staff_only=True,
        payload={
            "run": {"id": 2, "label": "news.fetch", "status": "failure"},
        },
    )
    one_cycle(monkeypatch)
    response = client.get("/api/app/ops/events", headers={"Last-Event-ID": str(cursor.pk)})
    assert read_changes(response) == [
        {
            "scope": "ops",
            "run": {"id": 2, "label": "news.fetch", "status": "failure"},
        }
    ]


def test_member_stream_never_contains_operational_data(client, member, monkeypatch):
    client.force_login(member)
    cursor = LiveEvent.objects.create(scope="news")
    LiveEvent.objects.create(scope="ops", staff_only=True, payload={"secret": "staff data"})
    LiveEvent.objects.create(scope="reports")
    one_cycle(monkeypatch)
    assert read_changes(
        client.get("/api/app/events", headers={"Last-Event-ID": str(cursor.pk)})
    ) == [{"scope": "reports"}]


def test_changes_arriving_after_connection_are_streamed(client, staff, monkeypatch):
    client.force_login(staff)
    one_cycle(monkeypatch)
    response = client.get("/api/app/ops/events")
    stream = iter(response.streaming_content)
    assert b"retry: 1000" in next(stream)
    assert b"event: ready" in next(stream)
    LiveEvent.objects.create(scope="reports")
    assert b'event: change\ndata: {"scope": "reports"}' in next(stream)
    response.close()


def test_idle_stream_only_heartbeats_without_refresh_ticks(monkeypatch):
    one_cycle(monkeypatch)
    chunks = "".join(live.event_stream(0, staff=True, resync=False))
    assert 'event: ready\ndata: {"resync": false}' in chunks
    assert ": heartbeat\n\n" in chunks
    assert "event: refresh" not in chunks
    assert "event: change" not in chunks
    assert "event: reconnect" in chunks


@pytest.mark.parametrize("history", ["initial", "current", "pruned", "reset"])
def test_ready_resyncs_only_when_replay_cannot_cover_the_connection(client, member, history):
    client.force_login(member)
    first = LiveEvent.objects.create(scope="news")
    second = LiveEvent.objects.create(scope="reports")
    latest = LiveEvent.objects.create(scope="companies")
    cursor = first.pk
    if history == "pruned":
        LiveEvent.objects.filter(pk__in=[first.pk, second.pk]).delete()
    if history == "reset":
        cursor = latest.pk + 1
    headers = {} if history == "initial" else {"Last-Event-ID": str(cursor)}
    response = client.get("/api/app/events", headers=headers)
    try:
        stream = iter(response.streaming_content)
        next(stream)
        ready = next(stream).decode()
        payload = json.loads(ready.split("data: ", 1)[1])
        assert payload == {"resync": history != "current"}
        expected_cursor = cursor if history == "current" else latest.pk
        assert ready.startswith(f"id: {expected_cursor}\n")
    finally:
        response.close()


def test_bulk_job_completion_invalidates_member_data(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        TaskRun.objects.create(
            task_id="bulk-live",
            task_name="fetch",
            label="News fetch",
            status=TaskRun.Status.SUCCESS,
            output="private result",
        )
    event = LiveEvent.objects.get(staff_only=False)
    assert event.scope == "all"
    assert event.payload == {}


@pytest.mark.parametrize("cursor", ["-1", "1\nid: 2", "x", "9" * 100, "\u0661"])
def test_invalid_cursor_is_a_problem_response(client, member, cursor):
    client.force_login(member)
    response = client.get("/api/app/events", headers={"Last-Event-ID": cursor})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_task_changes_publish_after_commit_without_output(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        run = TaskRun.objects.create(
            task_id="live-task", task_name="fetch", label="News fetch", output="private output"
        )
        assert not LiveEvent.objects.exists()
    event = LiveEvent.objects.get()
    assert event.staff_only
    assert event.payload == {"run": {"id": run.pk, "label": "News fetch", "status": "pending"}}
    with django_capture_on_commit_callbacks(execute=True):
        run.status = TaskRun.Status.SUCCESS
        run.save()
    assert LiveEvent.objects.order_by("-pk").first().payload["run"]["status"] == "success"


def test_rollback_does_not_publish(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True), transaction.atomic():
        live.publish("news")
        transaction.set_rollback(True)
    assert not LiveEvent.objects.exists()


def test_prune_cleans_replay_history_and_publishes_lost_jobs(django_capture_on_commit_callbacks):
    old = LiveEvent.objects.create(scope="news")
    LiveEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
    run = TaskRun.objects.create(task_id="lost-live", task_name="fetch", label="Lost job")
    TaskRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(hours=3))
    with django_capture_on_commit_callbacks(execute=True):
        result = prune()
    assert result["live_events"] == 1
    assert not LiveEvent.objects.filter(pk=old.pk).exists()
    assert LiveEvent.objects.filter(payload__run__status="failure").exists()
