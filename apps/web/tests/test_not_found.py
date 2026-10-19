"""Undefined browser URLs return a public themed 404, not a login or success."""

import pytest
from django.urls import reverse

from .test_public_preview import presentation

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("debug", [True, False])
@pytest.mark.parametrize(
    "path",
    [
        "/undefined/",
        "/undefined/deep/page/",
        "/app/undefined/",
        "/reports/not-a-date/",
        "/not-defined-without-slash",
        "/extra/",
        "/<script>alert(1)</script>/",
    ],
)
def test_undefined_urls_are_public_real_404s(client, settings, debug, path):
    settings.DEBUG = debug
    response = client.get(path)
    assert response.status_code == 404
    assert presentation(response)["page"] == "not-found"
    assert "Location" not in response
    assert "no-store" in response["Cache-Control"]
    assert "URL patterns" not in response.text
    assert "alert(1)" not in response.text


@pytest.mark.parametrize("method", ["get", "post", "head"])
def test_unknown_page_methods_do_not_become_successes(client, method):
    response = getattr(client, method)("/undefined/")
    assert response.status_code == 404


def test_authenticated_undefined_ops_paths_are_not_success_shells(client, django_user_model):
    user = django_user_model.objects.create_superuser("not-found-staff", password="test-only")
    client.force_login(user)
    for path in ["/ops/undefined/", "/ops/users/invalid/", "/ops/jobs/x/run/"]:
        response = client.get(path)
        assert response.status_code == 404
        assert presentation(response)["page"] == "not-found"


def test_missing_resources_use_the_same_404_in_production(client, django_user_model, settings):
    settings.DEBUG = False
    user = django_user_model.objects.create_superuser("missing-resource", password="test-only")
    client.force_login(user)
    for path in ["/ipos/999999/", "/reports/2000-01-01/", "/ops/runs/999999/"]:
        response = client.get(path)
        assert response.status_code == 404
        assert presentation(response)["page"] == "not-found"


def test_existing_routes_and_api_errors_are_not_swallowed(client, settings):
    settings.DEBUG = False
    assert client.get("/health/").json() == {"status": "ok"}
    assert client.get(reverse("web:landing")).status_code == 200
    assert client.get("/api/app/session").status_code == 401
    response = client.get("/api/nonexistent/")
    assert response.status_code == 404
    assert "public-preview" not in response.text
    assert client.get("/dashboard/").status_code == 302
