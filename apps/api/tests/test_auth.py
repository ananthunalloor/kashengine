import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.access.models import FeatureBlock
from apps.api import tokens
from apps.api.models import ApiToken
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db

PROBLEM = "application/problem+json"


def problem(response) -> dict:
    assert response["Content-Type"].startswith(PROBLEM)
    return json.loads(response.content)


def test_no_credentials_gives_401_problem():
    response = Client().get("/api/v1/me")
    body = problem(response)
    assert response.status_code == 401
    assert body["code"] == "unauthenticated"
    assert body["status"] == 401
    assert body["instance"] == "/api/v1/me"
    assert body["type"].endswith("#unauthenticated")
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_api_paths_never_redirect_to_the_login_page():
    response = Client().get("/api/v1/news")
    assert response.status_code == 401


def test_a_good_token_works(api):
    response = api("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["username"] == "member"
    assert response.json()["token"]["name"] == "test"
    assert "secret" not in json.dumps(response.json())


def test_a_session_works(member):
    client = Client()
    client.force_login(member)
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["token"] is None


def test_a_bad_token_is_401_and_never_falls_back_to_the_session(member):
    client = Client()
    client.force_login(member)
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer ke_bad"})
    assert response.status_code == 401
    assert problem(response)["code"] == "invalid_token"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Token abc", "bearer "])
def test_a_wrong_header_form_is_invalid_token(header):
    response = Client().get("/api/v1/me", headers={"Authorization": header})
    assert response.status_code == 401
    assert problem(response)["code"] == "invalid_token"


def test_an_expired_token_says_so(member, make_token, auth):
    row, raw = make_token(member)
    ApiToken.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    response = Client().get("/api/v1/me", headers=auth(raw))
    assert response.status_code == 401
    assert problem(response)["code"] == "token_expired"


def test_a_revoked_token_is_refused(member, make_token, auth):
    row, raw = make_token(member)
    tokens.revoke(row)
    response = Client().get("/api/v1/me", headers=auth(raw))
    assert problem(response)["code"] == "invalid_token"


def test_the_token_never_gives_more_access_than_the_user(member, make_token, auth, data):
    FeatureBlock.objects.create(user=member, feature="news")
    _row, raw = make_token(member)
    response = Client().get("/api/v1/news", headers=auth(raw))
    assert response.status_code == 403
    assert problem(response)["code"] == "feature_not_available"
    assert Client().get("/api/v1/ipos", headers=auth(raw)).status_code == 200


def test_the_subscription_rule_applies_to_the_api(api, member, expire, settings, data):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(member)
    response = api("/api/v1/reports")
    assert response.status_code == 403
    assert problem(response)["code"] == "subscription_required"
    # /me still works, so the user can see why.
    assert api("/api/v1/me").status_code == 200


def test_staff_need_no_subscription(staff_api, staff, expire, settings, data):
    settings.SUBSCRIPTIONS_REQUIRED = True
    conf.invalidate()
    expire(staff)
    assert staff_api("/api/v1/reports").status_code == 200


def test_an_inactive_user_with_a_session_is_refused(member):
    client = Client()
    client.force_login(member)
    member.is_active = False
    member.save()
    assert client.get("/api/v1/me").status_code == 401


def test_the_rate_limit(api, settings):
    settings.API_RATE_LIMIT_PER_MINUTE = 3
    conf.invalidate()
    codes = [api("/api/v1/me").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    blocked = api("/api/v1/me")
    body = problem(blocked)
    assert body["code"] == "rate_limited"
    assert 1 <= int(blocked["Retry-After"]) <= 61
    assert blocked["RateLimit-Remaining"] == "0"


def test_the_rate_limit_headers_show_the_state(api):
    response = api("/api/v1/me")
    assert response["RateLimit-Limit"] == "60"
    assert response["RateLimit-Remaining"] == "59"
    assert int(response["RateLimit-Reset"]) <= 61
    assert response["RateLimit-Policy"] == "60;w=60"


def test_each_token_has_its_own_counter(member, staff, make_token, auth, settings):
    settings.API_RATE_LIMIT_PER_MINUTE = 1
    conf.invalidate()
    _a, raw_a = make_token(member)
    _b, raw_b = make_token(staff)
    client = Client()
    assert client.get("/api/v1/me", headers=auth(raw_a)).status_code == 200
    assert client.get("/api/v1/me", headers=auth(raw_a)).status_code == 429
    assert client.get("/api/v1/me", headers=auth(raw_b)).status_code == 200


def test_failed_token_checks_block_the_address(settings):
    settings.API_AUTH_FAIL_LIMIT_PER_MINUTE = 3
    conf.invalidate()
    client = Client()
    bad = {"Authorization": "Bearer ke_" + "0" * 8 + "_" + "0" * 48}
    codes = [client.get("/api/v1/me", headers=bad).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 429, 429]


def test_a_failed_check_of_one_address_does_not_block_another(settings, member, make_token, auth):
    settings.API_AUTH_FAIL_LIMIT_PER_MINUTE = 1
    conf.invalidate()
    _row, raw = make_token(member)
    bad = {
        "Authorization": "Bearer ke_" + "0" * 8 + "_" + "0" * 48,
        "X-Forwarded-For": "203.0.113.5",
    }
    client = Client()
    client.get("/api/v1/me", headers=bad)
    assert client.get("/api/v1/me", headers=bad).status_code == 429
    good = {**auth(raw), "X-Forwarded-For": "203.0.113.9"}
    assert client.get("/api/v1/me", headers=good).status_code == 200
