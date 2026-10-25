"""Tests for the API token section of the Account page."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.api import tokens
from apps.api.models import ApiToken
from apps.delivery.models import DeliveryPreference
from apps.ops.models import AuditEvent

pytestmark = pytest.mark.django_db

PASSWORD = "pass-123-word"


@pytest.fixture(autouse=True)
def _setup(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    cache.clear()


@pytest.fixture
def user():
    account = get_user_model().objects.create_user("anan", password=PASSWORD)  # ty: ignore[unresolved-attribute]
    DeliveryPreference.objects.create(user=account, email_verified_at=timezone.now())
    return account


@pytest.fixture
def other():
    account = get_user_model().objects.create_user("other", password=PASSWORD)  # ty: ignore[unresolved-attribute]
    DeliveryPreference.objects.create(user=account, email_verified_at=timezone.now())
    return account


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


def test_account_page_shows_the_token_section(client_in):
    response = client_in.get(reverse("web:account"))
    assert response.status_code == 200
    assert b"API access" in response.content
    assert b"You have no API tokens." in response.content


def test_section_is_hidden_when_the_api_is_off(client_in, settings):
    settings.API_ENABLED = False
    response = client_in.get(reverse("web:account"))
    assert b"API access" not in response.content


def test_create_shows_the_token_once_and_stores_only_the_hash(client_in, user):
    response = client_in.post(reverse("web:token_create"), {"name": "Excel"})
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    row = ApiToken.objects.get(user=user)
    body = response.content.decode()
    assert f"ke_{row.prefix}_" in body
    secret = re.search(r"ke_[0-9a-f]{8}_[0-9a-f]{48}", body).group(0)  # ty: ignore[unresolved-attribute]
    assert row.token_hash == tokens.digest(secret)
    assert secret not in row.token_hash
    again = client_in.get(reverse("web:account"))
    assert secret not in again.content.decode()
    assert row.display in again.content.decode()


def test_create_is_audited_without_the_secret(client_in, user):
    client_in.post(reverse("web:token_create"), {"name": "Excel"})
    event = AuditEvent.objects.get(action="api token create")
    row = ApiToken.objects.get(user=user)
    assert event.actor == user
    assert row.display in event.detail
    assert not re.search(r"ke_[0-9a-f]{8}_[0-9a-f]{48}", event.detail)


def test_create_needs_post(client_in):
    assert client_in.get(reverse("web:token_create")).status_code == 405


def test_create_needs_sign_in(client):
    response = client.post(reverse("web:token_create"), {"name": "x"})
    assert response.status_code == 302
    assert "login" in response["Location"]
    assert not ApiToken.objects.exists()


def test_empty_name_shows_an_error_and_makes_no_token(client_in):
    response = client_in.post(reverse("web:token_create"), {"name": "   "})
    assert response.status_code == 200
    assert not ApiToken.objects.exists()


def test_limit_is_enforced(client_in, user, settings):
    settings.API_TOKEN_MAX_PER_USER = 1
    tokens.issue(user, "first")
    response = client_in.post(reverse("web:token_create"), {"name": "second"})
    assert response.status_code == 200
    assert ApiToken.objects.filter(user=user).count() == 1
    assert b"Revoke one" in response.content


def test_revoke_marks_the_token_and_audits(client_in, user):
    row, _secret = tokens.issue(user, "Excel")
    response = client_in.post(reverse("web:token_revoke", args=[row.pk]))
    assert response.status_code == 302
    assert response["Location"] == reverse("web:account")
    row.refresh_from_db()
    assert row.revoked_at is not None
    assert AuditEvent.objects.filter(action="api token revoke").count() == 1


def test_revoked_token_stops_working(client_in, client, user):
    row, secret = tokens.issue(user, "Excel")
    assert (
        client.get("/api/v1/me", headers={"Authorization": f"Bearer {secret}"}).status_code == 200
    )
    client_in.post(reverse("web:token_revoke", args=[row.pk]))
    assert (
        client.get("/api/v1/me", headers={"Authorization": f"Bearer {secret}"}).status_code == 401
    )


def test_a_user_cannot_revoke_the_token_of_another_user(client_in, other):
    row, _secret = tokens.issue(other, "Theirs")
    assert client_in.post(reverse("web:token_revoke", args=[row.pk])).status_code == 404
    row.refresh_from_db()
    assert row.revoked_at is None


def test_a_user_does_not_see_tokens_of_another_user(client_in, other):
    row, _secret = tokens.issue(other, "Theirs")
    assert row.display not in client_in.get(reverse("web:account")).content.decode()


def test_revoke_needs_post(client_in, user):
    row, _secret = tokens.issue(user, "Excel")
    assert client_in.get(reverse("web:token_revoke", args=[row.pk])).status_code == 405
