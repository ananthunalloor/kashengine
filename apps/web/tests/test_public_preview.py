"""Public React parity without replacing Django authentication or legacy URLs."""

import json
import re
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import URLPattern, resolve
from django.utils import timezone

from apps.access.models import FeatureBlock, Subscription
from apps.api.app.ops_pages import ACTIONS, PAGES
from apps.ops.urls import urlpatterns as ops_patterns
from apps.siteconfig import service
from apps.web.urls import urlpatterns as web_patterns

pytestmark = pytest.mark.django_db
PASSWORD = "preview-test-password"


def presentation(response):
    match = re.search(
        r'<script id="public-preview" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL,
    )
    assert match, "Missing safely encoded public React presentation."
    return json.loads(match[1])


@pytest.fixture
def member(django_user_model):
    return django_user_model.objects.create_user("preview-member", password=PASSWORD)


@pytest.mark.parametrize(("path", "page"), [("/app/landing/", "landing"), ("/app/login/", "login")])
def test_public_previews_are_anonymous_uncached_and_set_csrf(client, path, page):
    response = client.get(path)
    data = presentation(response)
    assert response.status_code == 200
    assert data["page"] == page
    assert data["authenticated"] is False
    assert data["csrf"]
    assert "csrftoken" in response.cookies
    assert {"private", "no-store"} <= set(response["Cache-Control"].split(", "))
    assert "web/public_preview.html" in [template.name for template in response.templates]
    assert "session" not in data


def test_landing_stays_public_after_expiry(client, member):
    service.save({"SUBSCRIPTIONS_REQUIRED": True})
    Subscription.objects.filter(user=member).update(ends_at=timezone.now() - timedelta(days=1))
    client.force_login(member)
    response = client.get("/app/landing/")
    assert response.status_code == 200
    assert presentation(response)["authenticated"] is True


@pytest.mark.parametrize("next_path", ["", "/app/news/?q=banks", "https://untrusted.invalid/"])
def test_login_uses_django_safe_redirects(client, member, next_path):
    response = client.post(
        "/app/login/", {"username": member.username, "password": PASSWORD, "next": next_path}
    )
    assert response.status_code == 302
    assert response["Location"] == (
        next_path if next_path.startswith("/app/") else "/app/dashboard/"
    )
    assert client.session["_auth_user_id"] == str(member.pk)


def test_invalid_login_never_serializes_credentials(client, member):
    response = client.post(
        "/app/login/", {"username": member.username, "password": "secret-invalid-password"}
    )
    assert response.status_code == 200
    assert presentation(response)["invalid"] is True
    assert member.username not in response.text
    assert "secret-invalid-password" not in response.text


def test_real_csrf_login_and_post_only_logout(member):
    client = Client(enforce_csrf_checks=True)
    assert (
        client.post("/app/login/", {"username": member.username, "password": PASSWORD}).status_code
        == 403
    )
    data = presentation(client.get("/app/login/"))
    response = client.post(
        "/app/login/",
        {"username": member.username, "password": PASSWORD, "csrfmiddlewaretoken": data["csrf"]},
    )
    assert response.status_code == 302
    assert client.get("/logout/").status_code == 405
    assert client.post("/logout/", {"next": "/app/login/"}).status_code == 403
    response = client.post(
        "/logout/",
        {"next": "/app/login/", "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
    )
    assert response.status_code == 302
    assert response["Location"] == "/app/login/"
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("minutes", [1, 30])
def test_real_axes_lockout_is_react_and_still_blocks_valid_credentials(client, member, minutes):
    service.save({"LOGIN_FAILURE_LIMIT": 1, "LOGIN_COOLOFF_MINUTES": minutes})
    response = client.post("/app/login/", {"username": member.username, "password": "wrong"})
    data = presentation(response)
    assert response.status_code == 429
    assert data["page"] == "lockout"
    assert data["minutes"] == (minutes or None)
    assert member.username not in response.text
    assert "wrong" not in response.text
    response = client.post("/app/login/", {"username": member.username, "password": PASSWORD})
    assert response.status_code == 429
    assert presentation(response)["page"] == "lockout"
    assert "_auth_user_id" not in client.session


def test_preview_feature_denial_keeps_real_403_and_legacy_template(client, member):
    FeatureBlock.objects.create(user=member, feature="news")
    client.force_login(member)
    preview = client.get("/app/news/")
    assert preview.status_code == 403
    assert presentation(preview)["feature"] == "News"
    legacy = client.get("/news/")
    assert legacy.status_code == 403
    assert "web/no_access.html" in [template.name for template in legacy.templates]


def test_preview_subscription_expiry_stays_in_react(client, member):
    service.save({"SUBSCRIPTIONS_REQUIRED": True})
    Subscription.objects.filter(user=member).update(ends_at=timezone.now() - timedelta(days=1))
    client.force_login(member)
    assert client.get("/app/news/")["Location"] == "/app/account/"
    assert client.get("/news/")["Location"] == "/account/"


@pytest.mark.parametrize(
    "path", ["/app/", "/app/reports/", "/app/ops/", "/app/ops/users/1/", "/app/ipos/1/"]
)
def test_preview_authentication_redirects_to_react_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == f"/app/login/?next={path}"


def test_ops_permission_denial_has_react_403(client, member):
    client.force_login(member)
    response = client.get("/app/ops/")
    assert response.status_code == 403
    assert presentation(response)["page"] == "access"


def test_all_legacy_product_pages_and_actions_have_react_equivalents():
    # Guard additions to the original URL inventory, not just the current preview routes.
    equivalents = {
        "landing": "/app/landing/",
        "login": "/app/login/",
        "logout": "/logout/",
        "dashboard": "/app/dashboard/",
        "reports": "/app/reports/",
        "report": "/app/reports/2026-10-19/",
        "news": "/app/news/",
        "ipos": "/app/ipos/",
        "ipo": "/app/ipos/1/",
        "markets": "/app/markets/",
        "companies": "/app/companies/",
        "delivery": "/app/delivery/",
        "account": "/app/account/",
        "token_create": "/api/app/account/tokens",
        "token_revoke": "/api/app/account/tokens/1/revoke",
    }
    legacy = {
        pattern.name
        for pattern in web_patterns
        if isinstance(pattern, URLPattern) and not pattern.name.startswith("react_")
    }
    assert legacy == set(equivalents)
    for path in equivalents.values():
        assert resolve(path)
    ops_names = {pattern.name for pattern in ops_patterns}
    assert ops_names == PAGES | ACTIONS | {"runs", "run", "audit"}
