"""The web app works behind Caddy (https://localhost/ in dev), which ends TLS."""

import re

import pytest
from django.test import Client

PROXY_HEADERS = {
    "Host": "localhost",
    "Origin": "https://localhost",
    "X-Forwarded-Proto": "https",
}


@pytest.mark.django_db
def test_login_post_passes_the_csrf_check_behind_caddy(django_user_model):
    django_user_model.objects.create_user("proxy-user", password="pw-proxy-test-1")
    client = Client(enforce_csrf_checks=True)

    page = client.get("/login/", headers=PROXY_HEADERS)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
    assert token is not None

    response = client.post(
        "/login/",
        {"username": "proxy-user", "password": "pw-proxy-test-1", "csrfmiddlewaretoken": token[1]},
        headers=PROXY_HEADERS,
    )

    assert response.status_code == 302


@pytest.mark.django_db
def test_login_post_from_a_wrong_origin_is_refused():
    client = Client(enforce_csrf_checks=True)
    headers = {**PROXY_HEADERS, "Origin": "https://evil.example"}

    response = client.post("/login/", {"username": "x", "password": "y"}, headers=headers)

    assert response.status_code == 403
