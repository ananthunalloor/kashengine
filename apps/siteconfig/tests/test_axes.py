"""django-axes: lock out an address after too many failed logins."""

from datetime import timedelta

import pytest
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.ops import users
from apps.siteconfig import axes_hooks, conf, service

pytestmark = pytest.mark.django_db

PASSWORD = "pw-lockout-test-1"


@pytest.fixture
def member(django_user_model):
    return django_user_model.objects.create_user("lockme", "l@example.com", PASSWORD)


def attempt(password: str, ip: str = "203.0.113.50") -> int:
    response = Client().post(
        reverse("web:login"),
        {"username": "lockme", "password": password},
        headers={"X-Forwarded-For": ip},
    )
    return response.status_code


def test_the_address_is_locked_after_the_limit(member):
    service.save({"LOGIN_FAILURE_LIMIT": 3})

    assert [attempt("bad") for _ in range(3)] == [200, 200, 429]
    assert attempt(PASSWORD) == 429  # The right password does not help during the lockout.


def test_another_address_can_still_log_in(member):
    service.save({"LOGIN_FAILURE_LIMIT": 2})
    for _ in range(2):
        attempt("bad", ip="203.0.113.50")

    assert attempt(PASSWORD, ip="198.51.100.9") == 302


def test_the_lockout_page_gives_no_details(member):
    service.save({"LOGIN_FAILURE_LIMIT": 1})

    response = Client().post(
        reverse("web:login"),
        {"username": "lockme", "password": "bad"},
        headers={"X-Forwarded-For": "203.0.113.51"},
    )
    page = response.content.decode()

    assert response.status_code == 429
    assert "Too many tries" in page
    assert "lockme" not in page
    assert "30 minute" in page


def test_the_limit_comes_from_the_dashboard_setting(member):
    assert axes_hooks.failure_limit(RequestFactory().get("/"), None) == conf.LOGIN_FAILURE_LIMIT
    service.save({"LOGIN_FAILURE_LIMIT": 9, "LOGIN_COOLOFF_MINUTES": 5})

    assert axes_hooks.failure_limit(RequestFactory().get("/"), None) == 9
    assert axes_hooks.cooloff(None) == timedelta(minutes=5)


def test_zero_minutes_means_until_an_admin_unlocks():
    service.save({"LOGIN_COOLOFF_MINUTES": 0})

    assert axes_hooks.cooloff(None) is None


def test_a_successful_login_resets_the_count(member):
    service.save({"LOGIN_FAILURE_LIMIT": 3})
    attempt("bad")
    attempt("bad")

    assert attempt(PASSWORD) == 302
    Client().get(reverse("web:login"))  # Nothing changes.
    assert [attempt("bad") for _ in range(2)] == [200, 200]  # The count started again.


def test_the_locked_address_is_listed_and_an_admin_can_unlock_it(member, django_user_model):
    service.save({"LOGIN_FAILURE_LIMIT": 2})
    for _ in range(2):
        attempt("bad", ip="203.0.113.77")
    assert attempt(PASSWORD, ip="203.0.113.77") == 429

    [row] = users.lockouts()
    assert row["ip_address"] == "203.0.113.77"
    assert row["failures"] >= 2
    assert row["until"] > timezone.now()

    boss = django_user_model.objects.create_superuser("boss", "b@example.com", PASSWORD)
    admin = Client()
    admin.force_login(boss)
    page = admin.get(reverse("ops:logins")).content.decode()
    assert "203.0.113.77" in page

    response = admin.post(reverse("ops:lockout_unlock"), {"ip_address": "203.0.113.77"})

    assert response.status_code == 302
    assert users.lockouts() == []
    assert attempt(PASSWORD, ip="203.0.113.77") == 302


def test_a_staff_user_cannot_unlock(member, django_user_model):
    staff = django_user_model.objects.create_user("st", password=PASSWORD, is_staff=True)
    client = Client()
    client.force_login(staff)

    response = client.post(reverse("ops:lockout_unlock"), {"ip_address": "203.0.113.77"})

    assert response.status_code == 403


def test_a_spoofed_forwarded_header_with_a_bad_address_does_not_break_the_login(member):
    response = Client().post(
        reverse("web:login"),
        {"username": "lockme", "password": PASSWORD},
        headers={"X-Forwarded-For": "not-an-ip"},
    )

    assert response.status_code == 302
