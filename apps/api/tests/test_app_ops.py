"""Staff-only run history, diagnostics, server tables, and preview isolation."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.ops.models import AuditEvent, TaskRun
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db
URL = "/api/app/ops/runs"


@pytest.fixture
def runs(staff):
    return [
        TaskRun.objects.create(
            task_id=f"run-{index}",
            task_name="apps.news.tasks.fetch",
            label="news.fetch" if index < 3 else "reports.build",
            status=status,
            trigger="manual" if index % 2 else "auto",
            triggered_by=staff if index % 2 else None,
            started_at=timezone.now() - timedelta(minutes=index) if index else None,
            duration_ms=None if index < 2 else index * 1000,
            worker="worker-one",
            args="stored arguments",
            result="stored result",
            error="<script>not executable</script>",
            output="stored output",
        )
        for index, status in enumerate(["pending", "started", "success", "failure"])
    ]


@pytest.mark.parametrize("path", [URL, f"{URL}/1"])
def test_anonymous_and_non_staff_never_query_runs(client, member, path):
    with patch.object(TaskRun.objects, "select_related", side_effect=AssertionError("Data read")):
        assert client.get(path).status_code == 401
        client.force_login(member)
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["detail"] == "Staff access is required for Ops."
        assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("superuser", [False, True])
def test_staff_can_read_without_public_api_or_subscription(
    client, staff, runs, settings, superuser
):
    staff.is_superuser = superuser
    staff.save(update_fields=["is_superuser"])
    settings.API_ENABLED = False
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    client.force_login(staff)
    response = client.get(URL)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert "ETag" not in response
    assert "API-Version" not in response
    body = response.json()
    assert body["labels"] == ["news.fetch", "reports.build"]
    assert body["total"] == 4
    assert [row["id"] for row in body["items"]] == [run.pk for run in reversed(runs)]
    assert body["retention_days"] == conf.OPS_RETENTION_DAYS
    assert body["page_size"] == conf.OPS_PAGE_SIZE
    for row in body["items"]:
        assert not {"args", "result", "error", "output", "worker", "task_id"} & row.keys()
    for run in runs:
        detail = client.get(f"{URL}/{run.pk}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["is_active"] == run.is_active
        assert data["error"] == run.error
        assert data["output"] == run.output
        assert data["result"] == run.result
        assert data["args"] == run.args
        assert data["task_id"] == run.task_id
        assert data["worker"] == run.worker
    assert not AuditEvent.objects.exists()


def test_query_filter_sort_and_pagination_apply_to_all_runs(client, staff, runs, settings):
    settings.OPS_PAGE_SIZE = 2
    conf.invalidate()
    client.force_login(staff)
    body = client.get(URL, {"sort": "duration_ms", "page_size": 1, "page": 2}).json()
    assert body["items"][0]["id"] == runs[3].pk
    assert body["items"][0]["duration"] == "3.0 s"
    assert body["total"] == 4
    assert body["pages"] == 4
    assert body["page"] == 2
    assert body["page_size"] == 1
    assert client.get(URL, {"q": "run-0"}).json()["items"][0]["id"] == runs[0].pk
    assert client.get(URL, {"q": "apps.news"}).json()["total"] == 4
    assert client.get(URL, {"q": " staff "}).json()["total"] == 2
    filtered = client.get(
        URL, {"label": "news.fetch", "status": "started", "trigger": "manual"}
    ).json()
    assert [row["id"] for row in filtered["items"]] == [runs[1].pk]
    assert filtered["labels"] == ["news.fetch", "reports.build"]
    assert client.get(URL, {"page": 999}).json()["page"] == 2
    assert client.get(URL, {"page": -3}).json()["page"] == 1
    assert client.get(URL, {"sort": "-duration_ms"}).json()["items"][0]["id"] == runs[3].pk


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "output"},
        {"status": "bogus"},
        {"trigger": "bogus"},
        {"page_size": 0},
        {"page_size": 101},
        {"q": "x" * 201},
    ],
)
def test_invalid_filters_are_visible(client, staff, params):
    client.force_login(staff)
    response = client.get(URL, params)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_empty_missing_deleted_actor_zero_and_stable_order(client, staff):
    client.force_login(staff)
    empty = client.get(URL).json()
    assert empty["items"] == []
    assert empty["total"] == 0
    assert empty["pages"] == 1
    assert client.get(f"{URL}/999").status_code == 404
    rows = [
        TaskRun.objects.create(
            task_id=f"tie-{index}", label="same", task_name="same", duration_ms=0, trigger="manual"
        )
        for index in range(2)
    ]
    data = client.get(URL, {"sort": "label"}).json()
    assert [row["id"] for row in data["items"]] == [row.pk for row in rows]
    assert data["items"][0]["duration"] == "0 ms"
    assert data["items"][0]["triggered_by"] is None


def test_bearer_and_inactive_sessions_cannot_read_runs(client, staff, runs, auth, make_token):
    _, secret = make_token(staff)
    client.force_login(staff)
    for path in [URL, f"{URL}/{runs[0].pk}"]:
        assert client.get(path, headers=auth(secret)).status_code == 401
    staff.is_active = False
    staff.save(update_fields=["is_active"])
    assert client.get(URL).status_code == 401


def test_preview_routes_are_staff_only_and_legacy_remains(client, member, staff, runs):
    for path in ["/ops/runs/", f"/ops/runs/{runs[0].pk}/"]:
        assert client.get(path).status_code == 302
        client.force_login(member)
        assert client.get(path).status_code == 403
        client.force_login(staff)
        response = client.get(path)
        assert response.status_code == 200
        assert b'id="root"' in response.content
        assert "no-store" in response["Cache-Control"]
        client.logout()
    client.force_login(staff)
    assert client.get("/ops/runs/999999/").status_code == 404
    assert "web/spa.html" in [t.name for t in client.get("/ops/runs/").templates]
    assert client.post(URL).status_code == 405


@pytest.fixture
def active_run():
    return TaskRun.objects.create(
        task_id="stop-me",
        task_name="apps.news.tasks.fetch",
        label="news.fetch",
        status=TaskRun.Status.STARTED,
        started_at=timezone.now(),
    )


def test_staff_who_is_not_a_superuser_cannot_stop_a_run(client, staff, active_run):
    client.force_login(staff)
    with patch("config.celery.app.control.revoke") as revoke:
        response = client.post(f"{URL}/{active_run.pk}/stop")

    assert response.status_code == 403
    assert response.json()["detail"] == "Only a superuser can stop a task run."
    revoke.assert_not_called()
    active_run.refresh_from_db()
    assert active_run.status == TaskRun.Status.STARTED
    assert not AuditEvent.objects.exists()


def test_superuser_stops_a_run_and_the_audit_trail_records_it(client, staff, active_run):
    staff.is_superuser = True
    staff.save(update_fields=["is_superuser"])
    client.force_login(staff)
    with patch("config.celery.app.control.revoke") as revoke:
        response = client.post(f"{URL}/{active_run.pk}/stop")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": TaskRun.Status.FAILURE}
    revoke.assert_called_once_with("stop-me", terminate=True, signal="SIGKILL")
    active_run.refresh_from_db()
    assert active_run.status == TaskRun.Status.FAILURE
    event = AuditEvent.objects.get()
    assert (event.actor, event.action, event.target) == (staff, "stop run", "news.fetch")


def test_a_run_that_is_not_active_is_not_stopped_again(client, staff, runs):
    staff.is_superuser = True
    staff.save(update_fields=["is_superuser"])
    client.force_login(staff)
    finished = next(run for run in runs if run.status == TaskRun.Status.SUCCESS)
    with patch("config.celery.app.control.revoke") as revoke:
        response = client.post(f"{URL}/{finished.pk}/stop")

    assert response.json() == {"ok": False, "status": TaskRun.Status.SUCCESS}
    revoke.assert_not_called()
