import pytest
from django.test import Client

from apps.api import versions
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db


def test_version_header(api):
    assert api("/api/v1/me")["API-Version"] == "1.0.0"


def test_answers_are_private_and_vary_by_credentials(api, data):
    response = api("/api/v1/news")
    assert response["Cache-Control"] == "private, max-age=0, must-revalidate"
    assert "Authorization" in response["Vary"]
    assert "Cookie" in response["Vary"]


def test_errors_are_never_cached():
    response = Client().get("/api/v1/me")
    assert response["Cache-Control"] == "no-store"


def test_etag_is_a_weak_tag(api, data):
    assert api("/api/v1/reports")["ETag"].startswith('W/"')


def test_conditional_get_returns_304(member, make_token, auth, data):
    _row, raw = make_token(member)
    client = Client()
    first = client.get("/api/v1/reports", headers=auth(raw))
    etag = first["ETag"]
    again = client.get("/api/v1/reports", headers={**auth(raw), "If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again["ETag"] == etag
    changed = client.get("/api/v1/reports", headers={**auth(raw), "If-None-Match": 'W/"other"'})
    assert changed.status_code == 200


def test_the_api_can_be_turned_off(api, settings):
    settings.API_ENABLED = False
    conf.invalidate()
    response = api("/api/v1/me")
    assert response.status_code == 503
    assert response.json()["code"] == "api_disabled"
    assert response["Retry-After"]
    assert Client().get("/health/").status_code == 200


def test_web_pages_are_not_touched_by_the_api_middleware(member):
    client = Client()
    client.force_login(member)
    response = client.get("/")
    assert "API-Version" not in response
    assert "RateLimit-Limit" not in response


def test_a_deprecated_version_sends_the_headers(api, monkeypatch):
    monkeypatch.setitem(
        versions.VERSIONS,
        "v1",
        versions.Version(
            "v1",
            "1.0.0",
            status="deprecated",
            deprecated_on="2027-01-01",
            sunset_on="2027-07-01",
            successor="v2",
        ),
    )
    response = api("/api/v1/me")
    assert response["Deprecation"] == "@1798761600"
    assert response["Sunset"] == "Thu, 01 Jul 2027 00:00:00 GMT"
    assert response["Link"] == '</api/v2/>; rel="successor-version"'


def test_a_stable_version_sends_no_deprecation_header(api):
    response = api("/api/v1/me")
    assert "Deprecation" not in response
    assert "Sunset" not in response


def test_an_unexpected_error_hides_its_cause(api, monkeypatch):
    def boom(*args, **kwargs):
        msg = "secret database host db.internal"
        raise RuntimeError(msg)

    monkeypatch.setattr("apps.api.v1.service.Access", boom)
    response = api("/api/v1/me")
    assert response.status_code == 500
    assert response.json()["code"] == "server_error"
    assert "db.internal" not in response.content.decode()
