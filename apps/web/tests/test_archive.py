"""Deployed host, authentication, role and action boundaries for the archived UI."""

import pytest
from django.test import Client
from django.urls import resolve

from apps.news.models import NewsFeed
from apps.siteconfig import service

from .test_public_preview import presentation

pytestmark = pytest.mark.django_db
PASSWORD = "archive-test-only"
ARCHIVE = "old.example.test"


@pytest.fixture(autouse=True)
def archive_settings(settings):
    settings.OLD_SITE_ADDRESS = ARCHIVE
    settings.ALLOWED_HOSTS = ["testserver", ARCHIVE, "old.localhost", "spoof.example.test"]


@pytest.fixture
def identities(django_user_model):
    return {
        "member": django_user_model.objects.create_user("archive-member", password=PASSWORD),
        "staff": django_user_model.objects.create_user(
            "archive-staff", password=PASSWORD, is_staff=True
        ),
        "superuser": django_user_model.objects.create_superuser("archive-super", password=PASSWORD),
    }


@pytest.mark.parametrize("role", ["anonymous", "member", "staff", "superuser"])
@pytest.mark.parametrize(
    "path", ["/", "/dashboard/", "/news/", "/account/", "/ops/feeds/", "/missing/"]
)
def test_every_archived_page_requires_an_active_superuser(client, identities, role, path):
    if role != "anonymous":
        client.force_login(identities[role])
    response = client.get(path, HTTP_HOST=ARCHIVE)
    assert response.status_code == (
        302
        if role == "anonymous"
        else 403
        if role != "superuser"
        else 404
        if path == "/missing/"
        else 200
    )
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    if role == "anonymous":
        assert response["Location"].startswith("/login/?next=")
    else:
        assert "Archived Django interface" in response.text
    if role == "superuser":
        assert 'id="root"' not in response.text


def test_archive_landing_links_product_pages_on_the_main_site(client, identities, settings):
    settings.SITE_ADDRESS = "kash.example.test"
    client.force_login(identities["superuser"])

    response = client.get("/", HTTP_HOST=ARCHIVE)

    for path in ("dashboard", "news", "markets", "ipos", "companies", "reports", "delivery"):
        assert f'href="http://kash.example.test/{path}/"' in response.text
        assert f'href="/{path}/"' not in response.text


@pytest.mark.parametrize("role", ["member", "staff", "superuser"])
def test_public_archive_login_never_establishes_sessions_for_non_superusers(
    client, identities, role
):
    page = client.get("/login/", HTTP_HOST=ARCHIVE)
    assert page.status_code == 200
    assert "Archived Django interface" in page.text
    response = client.post(
        "/login/",
        {"username": identities[role].username, "password": PASSWORD},
        HTTP_HOST=ARCHIVE,
    )
    if role == "superuser":
        assert response.status_code == 302
        assert response["Location"] == "/dashboard/"
        assert client.session["_auth_user_id"] == str(identities[role].pk)
    else:
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session
        assert "not correct" in response.text
    assert PASSWORD not in response.text


def test_inactive_superuser_cannot_login_or_reuse_a_session(client, identities):
    user = identities["superuser"]
    client.force_login(user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert client.get("/news/", HTTP_HOST=ARCHIVE).status_code == 302
    response = client.post(
        "/login/", {"username": user.username, "password": PASSWORD}, HTTP_HOST=ARCHIVE
    )
    assert response.status_code == 200
    assert "not correct" in response.text


def test_an_existing_staff_session_cannot_bypass_archive_checks(client, identities):
    user = identities["staff"]
    client.force_login(user)
    assert client.get("/ops/feeds/").status_code == 200
    assert client.get("/ops/feeds/", HTTP_HOST=ARCHIVE).status_code == 403
    assert client.get("/login/", HTTP_HOST=ARCHIVE).status_code == 200


@pytest.mark.parametrize("role", ["anonymous", "member", "staff", "superuser"])
def test_legacy_actions_only_run_for_superusers_on_archive_host(client, identities, role):
    if role != "anonymous":
        client.force_login(identities[role])
    payload = {
        "source": "Test",
        "name": "Archive feed",
        "url": "https://archive.example.test/feed.xml",
    }
    response = client.post("/ops/feeds/", payload, HTTP_HOST=ARCHIVE)
    assert response.status_code == (302 if role in {"anonymous", "superuser"} else 403)
    assert NewsFeed.objects.filter(name="Archive feed").exists() == (role == "superuser")


def test_main_routes_never_render_legacy_ui_or_accept_legacy_writes(client, identities):
    client.force_login(identities["superuser"])
    for path in ["/", "/dashboard/", "/news/", "/account/", "/ops/feeds/"]:
        response = client.get(path)
        assert response.status_code == 200
        assert 'id="root"' in response.text
        assert "Archived Django interface" not in response.text
    assert client.post("/ops/feeds/", {"name": "Must not save"}).status_code == 405
    assert not NewsFeed.objects.filter(name="Must not save").exists()
    assert client.post("/account/tokens/new/").status_code == 404
    assert client.post("/ops/feeds/1/delete/").status_code == 404
    for path in ["/app/", "/app/news/", "/app/ops/", "/app/login/"]:
        assert client.get(path).status_code == 404


def test_main_apis_reuse_original_handlers_without_exposing_them(client, identities):
    client.force_login(identities["superuser"])
    csrf = client.get("/api/app/session").cookies["csrftoken"].value
    response = client.post(
        "/api/app/ops/actions/feeds/",
        {"source": "Test", "name": "React feed", "url": "https://react.example.test/feed.xml"},
        headers={"X-CSRFToken": csrf},
    )
    assert response.status_code == 200
    assert response.json()["redirect"] == "/ops/feeds/"
    assert NewsFeed.objects.filter(name="React feed").exists()


def test_archive_csrf_login_and_action_boundary(identities):
    client = Client(enforce_csrf_checks=True)
    assert client.post("/login/", HTTP_HOST=ARCHIVE).status_code == 403
    page = client.get("/login/", HTTP_HOST=ARCHIVE)
    csrf = client.cookies["csrftoken"].value
    assert "csrftoken" in page.cookies
    assert not page.cookies["csrftoken"]["domain"]
    response = client.post(
        "/login/",
        {
            "username": identities["superuser"].username,
            "password": PASSWORD,
            "csrfmiddlewaretoken": csrf,
        },
        HTTP_HOST=ARCHIVE,
    )
    assert response.status_code == 302
    assert not response.cookies["sessionid"]["domain"]
    assert client.post("/ops/feeds/", HTTP_HOST=ARCHIVE).status_code == 403
    client.get("/ops/feeds/", HTTP_HOST=ARCHIVE)
    csrf = client.cookies["csrftoken"].value
    response = client.post(
        "/ops/feeds/",
        {
            "name": "CSRF feed",
            "source": "Test",
            "url": "https://csrf.example.test/feed.xml",
            "csrfmiddlewaretoken": csrf,
        },
        HTTP_HOST=ARCHIVE,
    )
    assert response.status_code == 302
    assert NewsFeed.objects.filter(name="CSRF feed").exists()


def test_archive_login_still_locks_out_after_failed_attempts(client, identities):
    service.save({"LOGIN_FAILURE_LIMIT": 2})
    data = {"username": identities["staff"].username, "password": PASSWORD}
    assert client.post("/login/", data, HTTP_HOST=ARCHIVE).status_code == 200
    response = client.post("/login/", data, HTTP_HOST=ARCHIVE)
    assert response.status_code == 429
    assert "Archived Django interface" in response.text
    assert (
        client.post(
            "/login/",
            {"username": identities["superuser"].username, "password": PASSWORD},
            HTTP_HOST=ARCHIVE,
        ).status_code
        == 429
    )


def test_forwarded_host_does_not_select_the_archive(client, identities):
    client.force_login(identities["member"])
    response = client.get("/news/", headers={"X-Forwarded-Host": ARCHIVE})
    assert response.status_code == 200
    assert 'id="root"' in response.text


def test_archive_is_selected_only_for_exact_configured_hostname(client, identities):
    client.force_login(identities["superuser"])
    assert (
        "Archived Django interface"
        in client.get("/news/", HTTP_HOST=f"{ARCHIVE.upper()}:8000").text
    )
    for host in ["testserver", "old.localhost", "spoof.example.test"]:
        response = client.get("/news/", HTTP_HOST=host)
        assert response.status_code == 200
        assert 'id="root"' in response.text


def test_archive_does_not_mount_main_api_or_admin(client, identities):
    client.force_login(identities["superuser"])
    for path in ["/api/app/session", "/api/v1/news", "/admin/", "/app/news/"]:
        response = client.get(path, HTTP_HOST=ARCHIVE)
        assert response.status_code == 404
        assert "Archived Django interface" in response.text
    assert client.get("/api/app/session").status_code == 200


def test_main_product_routes_resolve_to_react_only():
    for path in ["/news/", "/dashboard/", "/ops/jobs/", "/ops/settings/telegram/"]:
        match = resolve(path)
        assert match.func.__module__ == "apps.web.views"
    assert presentation(Client().get("/"))["page"] == "landing"
