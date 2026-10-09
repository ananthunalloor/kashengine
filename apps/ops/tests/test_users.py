"""Monitor the users and control their sessions."""

from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

from apps.ops import users
from apps.ops.models import LoginEvent

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def login(user, ip="203.0.113.5") -> Client:
    client = Client()
    client.post(
        "/login/",
        {"username": user.username, "password": PASSWORD},
        headers={"X-Forwarded-For": ip, "User-Agent": "Mozilla/5.0 Firefox/130"},
    )
    return client


def test_active_sessions_show_the_address_of_the_login(member):
    client = login(member)

    [session] = users.active_sessions()

    assert session.user_id == member.pk
    assert session.key == client.session.session_key
    assert session.ip_address == "203.0.113.5"
    assert "Firefox" in session.user_agent


def test_an_anonymous_session_is_not_listed(client):
    client.get("/login/")
    session = Session.objects.create(
        session_key="anon", session_data="", expire_date=timezone.now() + timedelta(days=1)
    )

    assert session.session_key not in {s.key for s in users.active_sessions()}


def test_an_expired_session_is_not_listed(member):
    login(member)
    Session.objects.update(expire_date=timezone.now() - timedelta(minutes=1))

    assert users.active_sessions() == []


def test_end_all_sessions_of_a_user(member, staff):
    login(member)
    login(member)
    login(staff)

    ended = users.end_user_sessions(member.pk)

    assert ended == 2
    assert [s.user_id for s in users.active_sessions()] == [staff.pk]


def test_the_own_session_is_not_ended(boss):
    client = login(boss)
    key = client.session.session_key or ""

    with pytest.raises(users.UserActionError):
        users.end_session(key, current_key=key)

    assert users.end_user_sessions(boss.pk, current_key=key) == 0
    assert len(users.active_sessions()) == 1


def test_a_user_that_is_turned_off_loses_the_sessions(member, boss):
    login(member)

    users.set_user_active(member, False, acting_user=boss)

    member.refresh_from_db()
    assert not member.is_active
    assert users.active_sessions() == []


def test_a_user_can_be_turned_on_again(member, boss):
    users.set_user_active(member, False, acting_user=boss)

    users.set_user_active(member, True, acting_user=boss)

    member.refresh_from_db()
    assert member.is_active


def test_an_admin_cannot_turn_off_the_own_account(boss, django_user_model):
    django_user_model.objects.create_superuser("other", "o@example.com", PASSWORD)

    with pytest.raises(users.UserActionError):
        users.set_user_active(boss, False, acting_user=boss)


def test_the_last_superuser_cannot_be_turned_off(boss, staff):
    with pytest.raises(users.UserActionError, match="last active superuser"):
        users.set_user_active(boss, False, acting_user=staff)

    boss.refresh_from_db()
    assert boss.is_active


def test_a_superuser_can_be_turned_off_when_another_is_active(boss, django_user_model):
    other = django_user_model.objects.create_superuser("other", "o@example.com", PASSWORD)

    users.set_user_active(boss, False, acting_user=other)

    boss.refresh_from_db()
    assert not boss.is_active


def test_users_with_stats(member, staff):
    login(member)
    login(member)
    Client().post("/login/", {"username": "member", "password": "wrong"})
    Client().post("/login/", {"username": "staff", "password": "wrong"})
    Client().post("/login/", {"username": "staff", "password": "wrong"})

    by_name = {u.username: u for u in users.users_with_stats()}

    assert by_name["member"].login_count == 2
    assert by_name["member"].failed_24h == 1
    assert by_name["staff"].login_count == 0
    assert by_name["staff"].failed_24h == 2


def test_users_with_stats_search(member, staff):
    assert [u.username for u in users.users_with_stats("MEMB")] == ["member"]
    assert [u.username for u in users.users_with_stats("staff@")] == ["staff"]


def test_login_event_filters(member):
    login(member, ip="198.51.100.7")
    Client().post(
        "/login/", {"username": "ghost", "password": "x"}, headers={"X-Forwarded-For": "192.0.2.1"}
    )

    assert users.login_events(kind="failed").count() == 1
    assert users.login_events(search="ghost").count() == 1
    assert users.login_events(search="198.51").count() == 1
    assert users.login_events(kind="nonsense").count() == 2
    assert users.login_events(hours=1).count() == 2
    old = LoginEvent.objects.latest("id")
    LoginEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=3))
    assert users.login_events(hours=24).count() == 1


def test_many_failed_logins_from_one_address_are_suspicious():
    for _ in range(users.SUSPICIOUS_FAILED_LOGINS):
        LoginEvent.objects.create(kind=LoginEvent.Kind.FAILED, username="a", ip_address="192.0.2.9")
    LoginEvent.objects.create(kind=LoginEvent.Kind.FAILED, username="a", ip_address="192.0.2.10")

    rows = users.failed_logins_by_address()

    assert rows[0] == {"ip_address": "192.0.2.9", "count": 5, "suspicious": True}
    assert rows[1]["suspicious"] is False
