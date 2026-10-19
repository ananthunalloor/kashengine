"""Audit preview permission matrix, legacy field parity, and server table behavior."""

from unittest.mock import patch

import pytest

from apps.ops.models import AuditEvent
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db
URL = "/api/app/ops/audit"
PREVIEW = "/ops/audit/"


@pytest.fixture
def events(staff):
    return [
        AuditEvent.objects.create(
            actor=staff if index % 2 else None,
            actor_name="staff" if index % 2 else "Deleted admin",
            action="run job" if index < 3 else "api token create",
            target=f"Target {index}",
            detail=f"<b>Detail {index}</b>",
            ip_address="2001:db8::1" if index % 2 else None,
        )
        for index in range(4)
    ]


def test_anonymous_and_non_staff_cannot_query_audit(client, member):
    with patch.object(AuditEvent.objects, "all", side_effect=AssertionError("Data read")):
        assert client.get(URL).status_code == 401
        assert client.get(PREVIEW).status_code == 302
        client.force_login(member)
        response = client.get(URL)
        assert response.status_code == 403
        assert response.json()["detail"] == "Staff access is required for Ops."
        assert response["Cache-Control"] == "private, no-store"
        assert client.get(PREVIEW).status_code == 403


@pytest.mark.parametrize("superuser", [False, True])
def test_staff_parity_cache_read_only_and_legacy(client, staff, events, settings, superuser):
    settings.API_ENABLED = False
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    staff.is_superuser = superuser
    staff.save(update_fields=["is_superuser"])
    client.force_login(staff)
    before = list(AuditEvent.objects.values())
    response = client.get(URL)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert "ETag" not in response
    assert "API-Version" not in response
    body = response.json()
    assert body["total"] == 4
    assert body["page_size"] == conf.OPS_PAGE_SIZE
    assert body["actors"] == ["Deleted admin", "staff"]
    assert body["actions"] == ["api token create", "run job"]
    for row, event in zip(body["items"], reversed(events), strict=True):
        assert set(row) == {
            "id",
            "created_at",
            "actor_name",
            "action",
            "target",
            "detail",
            "ip_address",
        }
        assert row["id"] == event.pk
        assert row["actor_name"] == event.actor_name
        assert row["detail"] == event.detail
        assert row["ip_address"] == event.ip_address
    preview = client.get(PREVIEW)
    assert preview.status_code == 200
    assert b'id="root"' in preview.content
    assert "no-store" in preview["Cache-Control"]
    assert "ops/audit.html" not in [t.name for t in preview.templates]
    assert client.post(URL).status_code == 405
    assert list(AuditEvent.objects.values()) == before


@pytest.mark.parametrize(
    ("query", "count"),
    [("DETAIL 0", 1), (" target 2 ", 1), ("Deleted admin", 2), ("2001:db8", 2), ("api token", 1)],
)
def test_search_all_display_fields(client, staff, events, query, count):
    client.force_login(staff)
    assert client.get(URL, {"q": query}).json()["total"] == count


def test_filters_sort_pagination_choices_and_deleted_actor(client, staff, events, settings):
    settings.OPS_PAGE_SIZE = 2
    conf.invalidate()
    client.force_login(staff)
    filtered = client.get(URL, {"actor": "staff", "action": "run job"}).json()
    assert [row["id"] for row in filtered["items"]] == [events[1].pk]
    assert filtered["actors"] == ["Deleted admin", "staff"]
    assert filtered["actions"] == ["api token create", "run job"]
    assert client.get(URL, {"actor": "does not exist"}).json()["total"] == 0
    body = client.get(URL, {"sort": "target", "page_size": 1, "page": 3}).json()
    assert [row["id"] for row in body["items"]] == [events[2].pk]
    assert body["pages"] == 4
    assert body["page_size"] == 1
    assert body["total"] == 4
    assert client.get(URL, {"page": 999}).json()["page"] == 2
    assert client.get(URL, {"page": -1}).json()["page"] == 1
    addresses = client.get(URL, {"sort": "-ip_address", "page_size": 10}).json()["items"]
    assert [row["id"] for row in addresses] == [
        events[1].pk,
        events[3].pk,
        events[0].pk,
        events[2].pk,
    ]
    assert (
        client.get(URL, {"sort": "actor_name"}).json()["items"][0]["actor_name"] == "Deleted admin"
    )


def test_actor_snapshot_survives_rename_and_deletion(client, staff, django_user_model):
    actor = django_user_model.objects.create_user("original-name")
    event = AuditEvent.objects.create(actor=actor, actor_name="original-name", action="change")
    actor.username = "new-name"
    actor.save(update_fields=["username"])
    client.force_login(staff)
    assert client.get(URL).json()["items"][0]["actor_name"] == "original-name"
    actor.delete()
    assert client.get(URL, {"actor": "original-name"}).json()["items"][0]["id"] == event.pk


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "detail"},
        {"page_size": 0},
        {"page_size": 101},
        {"q": "x" * 201},
        {"actor": "x" * 151},
        {"action": "x" * 51},
    ],
)
def test_invalid_filters_return_visible_validation(client, staff, params):
    client.force_login(staff)
    response = client.get(URL, params)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_empty_auth_and_budget(client, staff, make_token, auth, settings):
    client.force_login(staff)
    body = client.get(URL).json()
    assert body["items"] == []
    assert body["actions"] == body["actors"] == []
    assert body["total"] == 0
    assert body["pages"] == body["page"] == 1
    _, raw = make_token(staff)
    assert client.get(URL, headers=auth(raw)).status_code == 401
    settings.APP_API_RATE_LIMIT_PER_MINUTE = 1
    assert client.get(URL).status_code == 429
    staff.is_active = False
    staff.save(update_fields=["is_active"])
    assert client.get(URL).status_code == 401
