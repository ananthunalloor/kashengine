"""Ops controls for the API tokens of a user."""

import pytest
from django.urls import reverse

from apps.api import tokens
from apps.ops.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_staff_can_see_the_tokens_but_not_revoke(staff_client, member):
    row, secret = tokens.issue(member, "Excel")
    response = staff_client.get(reverse("ops:user", args=[member.pk]))
    body = response.content.decode()
    assert row.display in body
    assert secret not in body
    assert "Revoke all API tokens" not in body
    post = staff_client.post(reverse("ops:user_revoke_tokens", args=[member.pk]))
    assert post.status_code == 403
    row.refresh_from_db()
    assert row.revoked_at is None


def test_superuser_revokes_one_token(boss_client, member):
    first, _ = tokens.issue(member, "one")
    second, _ = tokens.issue(member, "two")
    response = boss_client.post(
        reverse("ops:user_revoke_tokens", args=[member.pk]), {"token": first.pk}
    )
    assert response.status_code == 302
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.revoked_at is not None
    assert second.revoked_at is None
    assert AuditEvent.objects.filter(action="revoke api tokens", target="member").count() == 1


def test_superuser_revokes_all_tokens(boss_client, member):
    tokens.issue(member, "one")
    tokens.issue(member, "two")
    boss_client.post(reverse("ops:user_revoke_tokens", args=[member.pk]))
    assert tokens.active_tokens(member) == []


def test_token_of_another_user_gives_404(boss_client, member, staff):
    row, _ = tokens.issue(staff, "x")
    response = boss_client.post(
        reverse("ops:user_revoke_tokens", args=[member.pk]), {"token": row.pk}
    )
    assert response.status_code == 404
    row.refresh_from_db()
    assert row.revoked_at is None


def test_bad_token_id_gives_404(boss_client, member):
    response = boss_client.post(
        reverse("ops:user_revoke_tokens", args=[member.pk]), {"token": "abc"}
    )
    assert response.status_code == 404


def test_turned_off_user_token_stops_working(boss_client, member, client):
    _row, secret = tokens.issue(member, "x")
    boss_client.post(reverse("ops:user_set_active", args=[member.pk]), {"active": "no"})
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {secret}"})
    assert response.status_code == 401
