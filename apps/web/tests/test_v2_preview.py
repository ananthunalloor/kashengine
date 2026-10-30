"""The V2 React shell under /v2/ remains staff-only while the UI is in review."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.delivery.models import DeliveryPreference

pytestmark = pytest.mark.django_db

PATHS = ["/v2/", "/v2/today/", "/v2/companies/sample/", "/v2/public/login/"]


def _login(client, *, staff: bool):
    account = get_user_model().objects.create_user(  # ty: ignore[unresolved-attribute]  # Django manager
        "staff" if staff else "member",
        password="pw-for-tests-only",  # noqa: S106
        is_staff=staff,
    )
    DeliveryPreference.objects.create(user=account, email_verified_at=timezone.now())
    client.force_login(account)


@pytest.mark.parametrize("path", PATHS)
def test_the_v2_preview_needs_a_login(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "/login/" in response["Location"]


@pytest.mark.parametrize("path", PATHS)
def test_the_v2_preview_is_closed_to_members(client, path):
    _login(client, staff=False)

    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", PATHS)
def test_the_v2_preview_serves_the_react_shell_to_staff(client, path):
    _login(client, staff=True)
    response = client.get(path)

    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert "no-store" in response["Cache-Control"]


def test_the_v2_preview_only_answers_safe_methods(client):
    _login(client, staff=True)

    assert client.post("/v2/today/").status_code == 405
