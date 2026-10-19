"""Permission, isolation, and contract tests for the private React API."""

import json
from pathlib import Path

import pytest
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from django.urls import reverse
from ninja.errors import HttpError

from apps.access import features
from apps.access.models import FeatureBlock
from apps.api.app.api import http_error
from apps.api.app.auth import AppSession
from apps.api.management.commands.export_openapi import render
from apps.siteconfig import conf
from apps.web.context import navigation_for

pytestmark = pytest.mark.django_db
SESSION_URL = "/api/app/session"


def test_anonymous_gets_a_problem_not_a_login_redirect(client):
    response = client.get(SESSION_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response["Content-Type"] == "application/problem+json"
    assert "Location" not in response
    assert "WWW-Authenticate" not in response


@pytest.mark.parametrize("with_session", [False, True])
def test_bearer_credentials_are_rejected(client, member, make_token, auth, with_session):
    _, secret = make_token(member)
    if with_session:
        client.force_login(member)

    response = client.get(SESSION_URL, headers=auth(secret))

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


@pytest.mark.parametrize("role", ["member", "staff", "superuser"])
def test_session_uses_the_existing_navigation_rules(client, django_user_model, role):
    user = django_user_model.objects.create_user(
        f"app-{role}",
        email=f"{role}@example.test",
        is_staff=role != "member",
        is_superuser=role == "superuser",
    )
    client.force_login(user)
    request = RequestFactory().get(SESSION_URL)
    request.user = user

    response = client.get(SESSION_URL)
    body = response.json()

    assert response.status_code == 200
    assert body["id"] == user.pk
    assert body["username"] == user.get_username()
    assert body["email"] == user.email
    assert body["is_staff"] == user.is_staff
    assert body["is_superuser"] == user.is_superuser
    assert body["features"] == sorted(features.KEYS)
    assert body["navigation"] == [
        {"label": link["label"], "url": link["url"]} for link in navigation_for(request)
    ]
    assert body["logout_url"] == reverse("web:logout")
    assert "csrftoken" in response.cookies
    assert response["Cache-Control"] == "private, no-store"
    assert "ETag" not in response
    assert "API-Version" not in response


def test_removed_features_are_not_advertised(client, member):
    FeatureBlock.objects.create(user=member, feature="news")
    client.force_login(member)

    body = client.get(SESSION_URL).json()

    assert "news" not in body["features"]
    assert "/news/" not in [link["url"] for link in body["navigation"]]


def test_expired_subscriber_can_load_the_shell_session(client, member, expire, settings):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(member)
    client.force_login(member)

    response = client.get(SESSION_URL)
    body = response.json()

    assert response.status_code == 200
    assert body["subscription_ok"] is False
    assert body["subscription_state"] == "expired"
    assert body["features"] == []
    assert body["notice"] == "Your access has ended."
    assert body["navigation"] == [{"label": "Account", "url": "/account/"}]


def test_inactive_sessions_cannot_read_the_private_api(client, member):
    client.force_login(member)
    member.is_active = False
    member.save(update_fields=["is_active"])

    assert client.get(SESSION_URL).status_code == 401


@pytest.mark.parametrize("superuser", [False, True])
def test_staff_remains_exempt_from_feature_and_subscription_restrictions(
    client, staff, expire, settings, superuser
):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    staff.is_superuser = superuser
    staff.save(update_fields=["is_superuser"])
    expire(staff)
    FeatureBlock.objects.create(user=staff, feature="news")
    client.force_login(staff)

    body = client.get(SESSION_URL).json()

    assert body["subscription_ok"] is True
    assert body["subscription_state"] == "staff"
    assert body["features"] == sorted(features.KEYS)
    assert "/ops/" in [item["url"] for item in body["navigation"]]


def test_private_api_still_works_when_public_api_is_disabled(client, member, settings):
    settings.API_ENABLED = False
    conf.invalidate()
    client.force_login(member)

    assert client.get(SESSION_URL).status_code == 200
    assert client.get("/api/v1/me").status_code == 503


def test_private_rate_budget_is_separate_from_public_budget(client, member, settings):
    settings.API_RATE_LIMIT_PER_MINUTE = 1
    settings.APP_API_RATE_LIMIT_PER_MINUTE = 2
    conf.invalidate()
    client.force_login(member)

    assert client.get("/api/v1/me").status_code == 200
    assert client.get("/api/v1/me").status_code == 429
    first = client.get(SESSION_URL)
    assert first.status_code == 200
    assert first["RateLimit-Limit"] == "2"
    assert client.get(SESSION_URL).status_code == 200
    response = client.get(SESSION_URL)
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response["Retry-After"]) > 0


def test_session_auth_enforces_csrf_on_unsafe_methods(member):
    request = RequestFactory().post("/api/app/example")
    request.user = member
    with pytest.raises(HttpError, match="CSRF check Failed"):
        AppSession()(request)


def test_session_auth_accepts_valid_csrf_on_unsafe_methods(member):
    request = RequestFactory().post("/api/app/example")
    request.user = member
    request.META["HTTP_X_CSRFTOKEN"] = get_token(request)
    request.COOKIES["csrftoken"] = request.META["CSRF_COOKIE"]

    assert AppSession()(request) == member


def test_csrf_errors_use_the_private_problem_contract():
    request = RequestFactory().post("/api/app/example")

    response = http_error(request, HttpError(403, "CSRF check Failed"))

    assert response.status_code == 403
    assert response["Content-Type"] == "application/problem+json"
    assert json.loads(response.content)["code"] == "csrf_failed"


def test_csrf_cookie_supports_existing_django_logout(member):
    client = Client(enforce_csrf_checks=True)
    client.force_login(member)
    response = client.get(SESSION_URL)
    assert client.post("/logout/").status_code == 403
    token = response.cookies["csrftoken"].value

    assert client.post("/logout/", headers={"X-CSRFToken": token}).status_code == 302
    assert client.get(SESSION_URL).status_code == 401


def test_private_contract_is_separate_and_committed():
    schema = json.loads(render("app"))
    committed = Path(__file__).resolve().parents[3] / "frontend" / "openapi" / "app.json"

    assert committed.read_text(encoding="utf-8") == render("app")
    assert set(schema["paths"]) == {
        SESSION_URL,
        "/api/app/reports",
        "/api/app/reports/{day}",
        "/api/app/news",
        "/api/app/ipos",
        "/api/app/ipos/{pk}",
        "/api/app/markets",
        "/api/app/companies",
        "/api/app/delivery",
        "/api/app/today",
        "/api/app/account",
        "/api/app/account/tokens",
        "/api/app/account/tokens/{pk}/revoke",
        "/api/app/ops/runs",
        "/api/app/ops/audit",
        "/api/app/ops/runs/{pk}",
        "/api/app/ops/pages/{path}",
        "/api/app/ops/actions/{path}",
    }
    assert set(schema["components"]["securitySchemes"]) == {"AppSession", "OpsSession"}
    assert "/api/app/session" not in json.loads(render("v1"))["paths"]
