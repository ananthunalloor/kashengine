"""Full workspace parity over existing domain handlers, with explicit safe JSON."""

import hashlib
import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.api.app.ops_pages import ACTIONS, PAGES, _job_statistics, form_data
from apps.delivery.models import SignupInvite
from apps.markets.models import Instrument
from apps.news.models import NewsFeed
from apps.ops import jobs, schedule
from apps.ops.forms import settings_form
from apps.ops.models import AuditEvent, TaskRun
from apps.siteconfig import registry

pytestmark = pytest.mark.django_db
BASE = "/api/app/ops/"


def test_job_statistics_have_numeric_counts_rates_and_formatted_durations(boss_client):
    job = jobs.JOBS[0]
    old = TaskRun.objects.create(
        task_id="old-job-stats",
        task_name=job.target,
        label=job.run_label,
        status="success",
        duration_ms=90000,
    )
    TaskRun.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=8))
    for index, (status, duration_ms) in enumerate(
        [("success", 0), ("failure", 2500), ("started", None), ("pending", None)]
    ):
        TaskRun.objects.create(
            task_id=f"job-stats-{index}",
            task_name=job.target,
            label=job.run_label,
            status=status,
            duration_ms=duration_ms,
        )
    body = boss_client.get(f"{BASE}pages/jobs/").json()
    summary = body["sections"][0]
    assert summary["title"] == "Job activity (last 7 days)"
    assert summary["details"]["Total runs"]["value"] == 4
    assert summary["details"]["Succeeded"]["value"] == 1
    assert summary["details"]["Failed"]["value"] == 1
    assert summary["details"]["Success rate"]["text"] == "50%"
    items = [
        item
        for section in body["sections"]
        if section["table"]
        for item in section["table"]["rows"]
    ]
    cells = next(item["cells"] for item in items if item["cells"]["job"]["text"] == job.label)
    assert "statistics" not in cells
    assert cells["runs_7d"]["value"] == 4
    assert cells["succeeded"]["tone"] == "positive"
    assert cells["failed"]["tone"] == "negative"
    assert cells["success_rate"]["text"] == "50%"
    assert cells["average_duration"]["text"] == "1.2 s"
    assert cells["maximum_duration"]["text"] == "2.5 s"
    assert cells["average_duration"]["value"] == 1250
    empty = next(item["cells"] for item in items if item["cells"]["job"]["text"] != job.label)
    assert empty["runs_7d"]["value"] == 0
    assert empty["success_rate"]["text"] == "No completed runs"
    assert empty["average_duration"]["value"] is None


@pytest.mark.parametrize(
    ("stats", "text", "tone"),
    [
        (None, "No completed runs", "neutral"),
        ({"runs": 2, "ok": 0, "failed": 0}, "No completed runs", "neutral"),
        ({"runs": 4, "ok": 1, "failed": 0, "avg_ms": 0}, "100%", "positive"),
        ({"runs": 1, "ok": 0, "failed": 1}, "0%", "negative"),
    ],
)
def test_job_success_rate_excludes_unfinished_runs_and_preserves_zero(stats, text, tone):
    cells = _job_statistics(stats)
    assert cells["success_rate"].text == text
    assert cells["success_rate"].tone == tone
    if stats and stats.get("avg_ms") == 0:
        assert cells["average_duration"].text == "0 ms"
        assert cells["average_duration"].value == 0


def test_metrics_uses_the_same_readable_job_statistics(boss_client, offline):
    TaskRun.objects.create(
        task_id="metrics-duration", task_name="test", label="test", status="failure", duration_ms=0
    )
    sections = boss_client.get(f"{BASE}pages/metrics/").json()["sections"]
    task_section = next(section for section in sections if section["title"] == "Jobs (7 days)")
    cells = task_section["table"]["rows"][0]["cells"]
    assert cells["failed"]["text"] == "1"
    assert cells["failed"]["tone"] == "negative"
    assert cells["success_rate"]["text"] == "0%"
    assert cells["average_duration"]["text"] == "0 ms"
    assert cells["maximum_duration"]["text"] == "0 ms"


@pytest.mark.parametrize(
    "path",
    [
        "overview/",
        "jobs/",
        "logs/",
        "metrics/",
        "users/",
        "invites/",
        "subscriptions/",
        "logins/",
        "config/",
        "settings/",
        "schedule/",
        "schedule/add/",
        "feeds/",
        "instruments/",
        "backups/",
    ],
)
def test_all_pages_are_typed_and_legacy_still_renders(boss_client, offline, path):
    response = boss_client.get(f"{BASE}pages/{path}")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["title"]
    assert isinstance(body["sections"], list)
    assert response["Cache-Control"] == "private, no-store"
    assert "ETag" not in response
    legacy = "/ops/" if path == "overview/" else f"/ops/{path}"
    assert boss_client.get(legacy).status_code == 200
    preview = "/ops/" if path == "overview/" else f"/ops/{path}"
    assert b'id="root"' in boss_client.get(preview).content


def test_every_settings_group_and_user_details(boss_client, member, offline):
    for group, _, _ in registry.GROUPS:
        response = boss_client.get(f"{BASE}pages/settings/{group}/")
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["sections"][0]["forms"][0]["fields"]
    response = boss_client.get(f"{BASE}pages/users/{member.pk}/")
    assert response.status_code == 200, response.content
    assert response.json()["title"] == member.username
    assert "password" not in response.json()["sections"][0]["details"]


def test_permission_matrix_and_action_allowlist(
    client, staff_client, member_client, boss_client, offline
):
    assert client.get(f"{BASE}pages/jobs/").status_code == 401
    assert member_client.get(f"{BASE}pages/jobs/").status_code == 403
    assert staff_client.get(f"{BASE}pages/jobs/").status_code == 200
    assert staff_client.get(f"{BASE}pages/backups/").status_code == 403
    assert staff_client.get("/ops/backups/").status_code == 403
    assert staff_client.post(f"{BASE}actions/feeds/", {}).status_code == 403
    assert boss_client.get(f"{BASE}pages/feeds/1/delete/").status_code == 404
    assert boss_client.post(f"{BASE}actions/users/", {}).status_code == 404
    assert (
        boss_client.get(f"{BASE}pages/jobs/", headers={"Authorization": "Bearer no"}).status_code
        == 401
    )
    assert "audit" not in PAGES  # Dedicated full-history endpoint remains authoritative.
    assert "feed_delete" in ACTIONS


def test_invites_table_contains_metadata_and_never_code_digests(boss_client, boss, member):
    available = SignupInvite(created_by=boss)
    code = available.generate_code()
    available.save()
    used = SignupInvite(created_by=boss, used_by=member, used_at=timezone.now())
    used.generate_code()
    used.save()
    revoked = SignupInvite(created_by=boss, revoked=True)
    revoked.generate_code()
    revoked.save()

    response = boss_client.get(f"{BASE}pages/invites/")
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    body = response.json()
    assert body["title"] == "Invite codes"
    section = body["sections"][0]
    assert section["forms"][0]["action"] == f"{BASE}actions/invites/generate/"
    rows = section["table"]["rows"]
    assert len(rows) == 3
    available_row = next(row for row in rows if row["cells"]["state"]["text"] == "Available")
    assert available_row["cells"]["invitation"]["text"] == f"#{available.pk}"
    assert available_row["cells"]["created_by"]["text"] == boss.username
    assert available_row["cells"]["created_at"]["kind"] == "time"
    assert available_row["forms"][0]["action"] == f"{BASE}actions/invites/{available.pk}/revoke/"
    used_row = next(row for row in rows if row["cells"]["state"]["text"] == "Used")
    assert used_row["cells"]["used_by"]["text"] == member.username
    assert used_row["cells"]["used_by"]["href"] == f"/ops/users/{member.pk}/"
    assert used_row["cells"]["email"]["text"] == member.email
    assert used_row["forms"] == []
    assert code not in response.content.decode()
    assert available.token_hash not in response.content.decode()
    assert boss_client.get("/ops/invites/").status_code == 200


def test_invites_empty_table_preserves_columns(boss_client):
    table = boss_client.get(f"{BASE}pages/invites/").json()["sections"][0]["table"]
    assert table["rows"] == []
    assert [column["key"] for column in table["columns"]] == [
        "invitation",
        "state",
        "created_at",
        "created_by",
        "used_at",
        "used_by",
        "email",
    ]


def test_invites_permissions_and_csrf(client, member_client, staff_client, boss_client):
    assert client.get(f"{BASE}pages/invites/").status_code == 401
    assert member_client.get(f"{BASE}pages/invites/").status_code == 403
    response = staff_client.get(f"{BASE}pages/invites/")
    assert response.status_code == 200
    assert response.json()["sections"][0]["forms"] == []
    assert staff_client.post(f"{BASE}actions/invites/generate/").status_code == 403
    assert member_client.post(f"{BASE}actions/invites/generate/").status_code == 403
    assert client.post(f"{BASE}actions/invites/generate/").status_code == 401
    protected = Client(enforce_csrf_checks=True)
    protected.cookies = boss_client.cookies
    assert protected.post(f"{BASE}actions/invites/generate/").status_code == 403
    assert not SignupInvite.objects.exists()


def test_invite_generation_and_revocation_are_audited_without_secrets(boss_client, boss):
    response = boss_client.post(f"{BASE}actions/invites/generate/")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"]
    assert body["redirect"] == "/ops/invites/"
    code = body["messages"][0]["text"].rsplit(": ", 1)[1]
    invite = SignupInvite.objects.get()
    assert invite.created_by == boss
    assert invite.token_hash == hashlib.sha256(code.encode()).hexdigest()
    event = AuditEvent.objects.get(action="generate invite")
    assert event.target == str(invite.pk)
    assert code not in event.detail
    assert invite.token_hash not in event.detail
    listing = boss_client.get(f"{BASE}pages/invites/")
    assert code not in listing.content.decode()
    assert "messages" not in listing.json()
    response = boss_client.post(f"{BASE}actions/invites/{invite.pk}/revoke/")
    assert response.json()["ok"]
    invite.refresh_from_db()
    assert invite.revoked
    assert AuditEvent.objects.filter(action="revoke invite", target=str(invite.pk)).count() == 1
    response = boss_client.post(f"{BASE}actions/invites/{invite.pk}/revoke/")
    assert not response.json()["ok"]
    assert AuditEvent.objects.filter(action="revoke invite").count() == 1


def test_used_invites_cannot_be_revoked_or_regenerated(boss_client, boss, member):
    invite = SignupInvite(created_by=boss, used_by=member, used_at=timezone.now())
    invite.generate_code()
    invite.save()
    response = boss_client.post(f"{BASE}actions/invites/{invite.pk}/revoke/")
    assert not response.json()["ok"]
    invite.refresh_from_db()
    assert not invite.revoked
    assert invite.used_by == member
    assert not AuditEvent.objects.filter(action="revoke invite").exists()
    with pytest.raises(ValueError, match="existing invitation"):
        invite.generate_code()
    assert boss_client.post(f"{BASE}actions/invites/999999/revoke/").status_code == 404


def test_invite_table_search_filter_sort_and_pagination(boss_client, boss, member):
    for index in range(3):
        invite = SignupInvite(created_by=boss, revoked=index == 2)
        invite.generate_code()
        invite.save()
    invite = SignupInvite(created_by=boss, used_by=member, used_at=timezone.now())
    invite.generate_code()
    invite.save()
    response = boss_client.get(
        f"{BASE}pages/invites/", {"state": "Available", "sort": "-created_at", "page_size": 1}
    )
    table = response.json()["sections"][0]["table"]
    assert table["total"] == 2
    assert table["pages"] == 2
    assert table["rows"][0]["cells"]["state"]["text"] == "Available"
    assert table["filter_choices"]["state"] == ["Available", "Revoked", "Used"]
    response = boss_client.get(f"{BASE}pages/invites/", {"q": member.email})
    table = response.json()["sections"][0]["table"]
    assert table["total"] == 1
    assert table["rows"][0]["cells"]["used_by"]["text"] == member.username


def test_form_validation_errors_and_no_secret_echo(boss_client):
    response = boss_client.post(
        f"{BASE}actions/feeds/", {"source": "Test", "name": "Feed", "url": "file:///private"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["page"]["sections"][0]["forms"][0]["fields"][2]["errors"]
    response = boss_client.post(
        f"{BASE}actions/backups/settings/",
        {
            "timezone": "not-a-zone",
            "access_key": "never-echo-this",
            "secret_key": "never-echo-that",
        },
    )
    assert response.status_code == 200, response.content
    assert response.json()["ok"] is False
    assert "never-echo" not in response.content.decode()


def test_feed_actions_stay_in_react_and_audit_once(boss_client):
    before = AuditEvent.objects.count()
    response = boss_client.post(
        f"{BASE}actions/feeds/",
        {
            "source": "Test",
            "name": "<b>Feed</b>",
            "url": "https://example.test/feed.xml",
        },
    )
    assert response.status_code == 200, response.content
    assert response.json()["ok"] is True
    assert response.json()["redirect"] == "/ops/feeds/"
    assert AuditEvent.objects.count() == before + 1
    feed = NewsFeed.objects.get(name="<b>Feed</b>")
    response = boss_client.post(f"{BASE}actions/feeds/{feed.pk}/toggle/")
    assert response.json()["ok"]
    feed.refresh_from_db()
    assert feed.enabled is False
    assert boss_client.post(f"{BASE}actions/feeds/{feed.pk}/delete/").json()["ok"]
    assert not NewsFeed.objects.filter(pk=feed.pk).exists()


def test_server_search_filter_sort_pagination_and_empty_lists(boss_client):
    NewsFeed.objects.all().delete()
    for index in range(25):
        NewsFeed.objects.create(
            source="Test", name=f"Feed {index:02}", url=f"https://example.test/{index}"
        )
    endpoint = f"{BASE}pages/feeds/"
    table = boss_client.get(endpoint, {"page": 2, "page_size": 10, "sort": "-name"}).json()[
        "sections"
    ][0]["table"]
    assert table["total"] == 25
    assert len(table["rows"]) == 10
    assert table["rows"][0]["cells"]["name"]["text"] == "Feed 14"
    assert table["filter_choices"]["state"] == ["On"]
    result = boss_client.get(endpoint, {"q": "Feed 24"}).json()["sections"][0]["table"]
    assert result["total"] == 1
    assert boss_client.get(endpoint, {"state": "Off"}).json()["sections"][0]["table"]["rows"] == []
    assert boss_client.get(endpoint, {"page": "broken"}).status_code == 422


def test_staff_forms_are_absent_and_reads_do_not_audit(staff_client, member, offline):
    before = AuditEvent.objects.count()
    for path in (
        "jobs/",
        "users/",
        f"users/{member.pk}/",
        "feeds/",
        "instruments/",
        "schedule/",
        "settings/",
    ):
        body = staff_client.get(f"{BASE}pages/{path}").json()
        for section in body["sections"]:
            assert section["forms"] == []
            if section["table"]:
                assert all(not row["forms"] for row in section["table"]["rows"])
    assert AuditEvent.objects.count() == before


def test_writes_require_csrf(boss):
    client = Client(enforce_csrf_checks=True)
    client.force_login(boss)
    assert client.post(f"{BASE}actions/feeds/", {}).status_code == 403
    client.get("/api/app/session")
    response = client.post(
        f"{BASE}actions/feeds/", {}, headers={"X-CSRFToken": client.cookies["csrftoken"].value}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_job_confirm_busy_and_dispatch_feedback(boss_client, queue):
    job = next(job for job in jobs.JOBS if job.confirm)
    endpoint = f"{BASE}actions/jobs/{job.key}/run/"
    assert boss_client.post(endpoint).json()["ok"] is False
    response = boss_client.post(endpoint, {"confirm": "yes"})
    assert response.json()["ok"] is True
    assert response.json()["redirect"] == "/ops/jobs/"
    assert len(queue) == 1
    assert boss_client.post(endpoint, {"confirm": "yes"}).json()["messages"]


def test_session_actions_never_expose_usable_session_keys(boss_client, member):
    other = Client()
    other.force_login(member)
    key = other.session.session_key
    endpoint = f"{BASE}pages/users/{member.pk}/"
    body = boss_client.get(endpoint).json()
    assert key not in json.dumps(body)
    sessions = next(s for s in body["sections"] if s["title"] == "Open sessions")
    opaque = sessions["table"]["rows"][0]["forms"][0]["fields"][0]["value"]
    response = boss_client.post(
        f"{BASE}actions/users/{member.pk}/sessions/end/", {"session": opaque}
    )
    assert response.json()["ok"]
    assert (
        boss_client.post(f"{BASE}actions/users/{member.pk}/sessions/end/", {"key": key}).status_code
        == 403
    )


def test_secret_settings_fields_never_echo_input(boss_client):
    group = next(
        group for group, _, _ in registry.GROUPS if any(s.secret for s in registry.specs_in(group))
    )
    form = settings_form(group)()
    secret = next(s.key for s in registry.specs_in(group) if s.secret)
    form = settings_form(group)({secret: "do-not-serialize"})
    result = form_data(form, f"settings/{group}/", "Save")
    assert "do-not-serialize" not in result.model_dump_json()


def test_checkbox_fields_can_turn_a_saved_false_value_on(boss_client):
    instrument = Instrument.objects.create(
        symbol="FALSE", name="Disabled", kind="cue", enabled=False
    )
    response = boss_client.get(f"{BASE}pages/instruments/").json()
    item = next(
        item
        for item in response["sections"][0]["table"]["rows"]
        if item["cells"]["symbol"]["text"] == "FALSE"
    )
    form = item["forms"][0]
    enabled = next(field for field in form["fields"] if field["name"].endswith("-enabled"))
    assert enabled["checked"] is False
    assert enabled["value"] == "on"
    payload = {field["name"]: field["value"] for field in form["fields"]}
    assert boss_client.post(form["action"], payload).json()["ok"]
    instrument.refresh_from_db()
    assert instrument.enabled


def test_schedule_create_edit_toggle_delete_and_reset_confirmation(boss_client):
    task = next(iter(schedule.schedulable_tasks()))
    payload = {
        "name": "React test",
        "task": task,
        "minute": "15",
        "hour": "8",
        "day_of_week": "mon-fri",
        "day_of_month": "*",
        "month": "*",
        "enabled": "on",
    }
    response = boss_client.post(f"{BASE}actions/schedule/add/", payload)
    assert response.json()["ok"], response.content
    entry = next(
        entry for entry in schedule.entries(enabled_only=False) if entry.name == "React test"
    )
    assert boss_client.get(f"{BASE}pages/schedule/{entry.pk}/").status_code == 200
    payload["hour"] = "9"
    assert boss_client.post(f"{BASE}actions/schedule/{entry.pk}/", payload).json()["ok"]
    assert boss_client.post(f"{BASE}actions/schedule/{entry.pk}/toggle/").json()["ok"]
    assert boss_client.post(f"{BASE}actions/schedule/{entry.pk}/delete/").json()["ok"]
    assert boss_client.post(f"{BASE}actions/schedule/reset/").json()["ok"] is False
    assert boss_client.post(f"{BASE}actions/schedule/reset/", {"confirm": "yes"}).json()["ok"]


def test_user_actions_preserve_self_protection_access_and_subscription_rules(
    boss_client, boss, member
):
    assert (
        boss_client.post(f"{BASE}actions/users/{boss.pk}/active/", {"active": "no"}).json()["ok"]
        is False
    )
    assert boss_client.post(f"{BASE}actions/users/{member.pk}/active/", {"active": "no"}).json()[
        "ok"
    ]
    member.refresh_from_db()
    assert not member.is_active
    assert boss_client.post(f"{BASE}actions/users/{member.pk}/active/", {"active": "yes"}).json()[
        "ok"
    ]
    assert boss_client.post(f"{BASE}actions/users/{member.pk}/access/", {"allow": ["news"]}).json()[
        "ok"
    ]
    assert boss_client.post(
        f"{BASE}actions/users/{member.pk}/subscription/give/",
        {"kind": "paid", "days": "30", "note": "React test"},
    ).json()["ok"]
    assert (
        boss_client.post(
            f"{BASE}actions/users/{member.pk}/subscription/give/", {"kind": "paid", "days": "0"}
        ).json()["ok"]
        is False
    )
    assert boss_client.post(f"{BASE}actions/users/{member.pk}/subscription/end/").json()["ok"]


@pytest.mark.django_db(transaction=True)
def test_backup_round_trip_uses_streaming_download_and_signs_out_after_restore(boss_client):
    response = boss_client.post(f"{BASE}actions/backups/export/")
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["Cache-Control"] == "private, no-store"
    payload = b"".join(response.streaming_content)
    response.close()
    feed = NewsFeed.objects.create(
        source="Temporary", name="After export", url="https://example.test/after"
    )
    invalid = boss_client.post(
        f"{BASE}actions/backups/import/",
        {
            "backup": SimpleUploadedFile("snapshot.json", payload, content_type="application/json"),
            "confirmation": "wrong",
        },
    )
    assert invalid.status_code == 200
    assert invalid.json()["ok"] is False
    assert NewsFeed.objects.filter(pk=feed.pk).exists()
    restored = boss_client.post(
        f"{BASE}actions/backups/import/",
        {
            "backup": SimpleUploadedFile("snapshot.json", payload, content_type="application/json"),
            "confirmation": "RESTORE",
        },
    )
    assert restored.status_code == 200, restored.content
    assert restored.json()["ok"]
    assert restored.json()["redirect"] == "/login/"
    assert not NewsFeed.objects.filter(name="After export").exists()
    assert boss_client.get("/api/app/session").status_code == 401
