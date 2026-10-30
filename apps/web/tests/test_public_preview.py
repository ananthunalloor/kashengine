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
from apps.delivery.models import DeliveryPreference
from apps.ops.urls import urlpatterns as ops_patterns
from apps.siteconfig import service
from apps.web.legacy_urls import urlpatterns as web_patterns

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
    user = django_user_model.objects.create_user("preview-member", password=PASSWORD)
    DeliveryPreference.objects.create(user=user, email_verified_at=timezone.now())
    return user


@pytest.mark.parametrize(("path", "page"), [("/", "landing"), ("/login/", "login")])
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
    response = client.get("/")
    assert response.status_code == 200
    assert presentation(response)["authenticated"] is True


@pytest.mark.parametrize("next_path", ["", "/news/?q=banks", "https://untrusted.invalid/"])
def test_login_uses_django_safe_redirects(client, member, next_path):
    response = client.post(
        "/login/", {"username": member.username, "password": PASSWORD, "next": next_path}
    )
    assert response.status_code == 302
    assert response["Location"] == (next_path if next_path.startswith("/") else "/dashboard/")
    assert client.session["_auth_user_id"] == str(member.pk)


def test_invalid_login_never_serializes_credentials(client, member):
    response = client.post(
        "/login/", {"username": member.username, "password": "secret-invalid-password"}
    )
    assert response.status_code == 200
    assert presentation(response)["invalid"] is True
    assert member.username not in response.text
    assert "secret-invalid-password" not in response.text


def test_real_csrf_login_and_post_only_logout(member):
    client = Client(enforce_csrf_checks=True)
    assert (
        client.post("/login/", {"username": member.username, "password": PASSWORD}).status_code
        == 403
    )
    data = presentation(client.get("/login/"))
    response = client.post(
        "/login/",
        {"username": member.username, "password": PASSWORD, "csrfmiddlewaretoken": data["csrf"]},
    )
    assert response.status_code == 302
    assert client.get("/logout/").status_code == 405
    assert client.post("/logout/", {"next": "/login/"}).status_code == 403
    response = client.post(
        "/logout/",
        {"next": "/login/", "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
    )
    assert response.status_code == 302
    assert response["Location"] == "/login/"
    assert "_auth_user_id" not in client.session


@pytest.mark.parametrize("minutes", [1, 30])
def test_real_axes_lockout_is_react_and_still_blocks_valid_credentials(client, member, minutes):
    service.save({"LOGIN_FAILURE_LIMIT": 1, "LOGIN_COOLOFF_MINUTES": minutes})
    response = client.post("/login/", {"username": member.username, "password": "wrong"})
    data = presentation(response)
    assert response.status_code == 429
    assert data["page"] == "lockout"
    assert data["minutes"] == (minutes or None)
    assert member.username not in response.text
    assert "wrong" not in response.text
    response = client.post("/login/", {"username": member.username, "password": PASSWORD})
    assert response.status_code == 429
    assert presentation(response)["page"] == "lockout"
    assert "_auth_user_id" not in client.session


def test_feature_denial_keeps_real_403_without_exposing_legacy_template(client, member):
    FeatureBlock.objects.create(user=member, feature="news")
    client.force_login(member)
    preview = client.get("/news/")
    assert preview.status_code == 403
    assert presentation(preview)["feature"] == "News"
    assert "web/no_access.html" not in [template.name for template in preview.templates]


def test_preview_subscription_expiry_stays_in_react(client, member):
    service.save({"SUBSCRIPTIONS_REQUIRED": True})
    Subscription.objects.filter(user=member).update(ends_at=timezone.now() - timedelta(days=1))
    client.force_login(member)
    assert client.get("/news/")["Location"] == "/account/"
    assert client.get("/news/")["Location"] == "/account/"


@pytest.mark.parametrize("path", ["/dashboard/", "/reports/", "/ops/", "/ops/users/1/", "/ipos/1/"])
def test_preview_authentication_redirects_to_react_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == f"/login/?next={path}"


def test_ops_permission_denial_has_react_403(client, member):
    client.force_login(member)
    response = client.get("/ops/")
    assert response.status_code == 403
    assert presentation(response)["page"] == "access"


def test_all_legacy_product_pages_and_actions_have_react_equivalents():
    # Guard additions to the original URL inventory, not just the current preview routes.
    equivalents = {
        "landing": "/",
        "login": "/login/",
        "logout": "/logout/",
        "dashboard": "/dashboard/",
        "reports": "/reports/",
        "report": "/reports/2026-10-19/",
        "news": "/news/",
        "ipos": "/ipos/",
        "ipo": "/ipos/1/",
        "markets": "/markets/",
        "companies": "/companies/",
        "watchlist": "/watchlist/",
        "delivery": "/delivery/",
        "account": "/account/",
        "token_create": "/api/app/account/tokens",
        "token_revoke": "/api/app/account/tokens/1/revoke",
    }
    legacy = {
        pattern.name
        for pattern in web_patterns
        if isinstance(pattern, URLPattern) and not str(pattern.name).startswith("react_")
    }
    assert legacy == set(equivalents)
    for path in equivalents.values():
        assert resolve(path)
    ops_names = {pattern.name for pattern in ops_patterns}
    assert ops_names == PAGES | ACTIONS | {"runs", "run", "run_stop", "audit"}


def test_main_product_routes_never_resolve_to_legacy_views():
    for path in ["/dashboard/", "/news/", "/ipos/", "/ops/feeds/"]:
        assert resolve(path).func.__module__ == "apps.web.views"
