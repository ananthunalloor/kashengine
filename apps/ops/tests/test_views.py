"""The Ops pages: access rules, content, and the actions."""

import pytest
from django.contrib.sessions.models import Session
from django.test import Client
from django.urls import reverse

from apps.ops import audit
from apps.ops.models import AuditEvent, LoginEvent, TaskRun

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

DS = {"Datastar-Request": "true"}
PAGES = [
    "ops:overview",
    "ops:jobs",
    "ops:runs",
    "ops:logs",
    "ops:metrics",
    "ops:users",
    "ops:logins",
    "ops:audit",
    "ops:config",
]


# Access


@pytest.mark.parametrize("name", PAGES)
def test_an_anonymous_user_is_sent_to_the_login(client, name):
    response = client.get(reverse(name))

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.parametrize("name", PAGES)
def test_a_normal_user_gets_a_403(member_client, name):
    assert member_client.get(reverse(name)).status_code == 403


@pytest.mark.parametrize("name", PAGES)
def test_a_staff_user_can_open_every_page(staff_client, offline, name):
    assert staff_client.get(reverse(name)).status_code == 200


@pytest.mark.parametrize("name", PAGES)
def test_a_superuser_can_open_every_page(boss_client, offline, name):
    assert boss_client.get(reverse(name)).status_code == 200


def test_the_detail_pages_follow_the_same_rules(
    client, member_client, staff_client, staff, offline
):
    run = TaskRun.objects.create(task_id="r1", task_name="a", label="a")
    urls = [reverse("ops:run", args=[run.pk]), reverse("ops:user", args=[staff.pk])]

    for url in urls:
        assert client.get(url).status_code == 302
        assert member_client.get(url).status_code == 403
        assert staff_client.get(url).status_code == 200


def test_the_menu_shows_the_ops_link_to_staff_only(staff_client, member_client, offline):
    ops = reverse("ops:overview")

    assert f'href="{ops}"' in staff_client.get(reverse("web:dashboard")).content.decode()
    assert f'href="{ops}"' not in member_client.get(reverse("web:dashboard")).content.decode()


def test_the_ops_pages_have_their_own_menu(staff_client, offline):
    page = staff_client.get(reverse("ops:jobs")).content.decode()

    for name in PAGES:
        assert f'href="{reverse(name)}"' in page


def test_a_staff_user_does_not_see_the_run_buttons(staff_client, boss_client, offline):
    url = reverse("ops:jobs")
    action = reverse("ops:job_run", args=["news-fetch"])

    assert action not in staff_client.get(url).content.decode()
    assert action in boss_client.get(url).content.decode()


# Overview


def test_the_overview_gives_a_partial_to_datastar(staff_client, offline):
    full = staff_client.get(reverse("ops:overview")).content.decode()
    partial = staff_client.get(reverse("ops:overview"), headers=DS).content.decode()

    assert "<html" in full
    assert "<html" not in partial
    assert 'id="health-panel"' in partial
    assert 'id="health-panel"' in full


def test_the_overview_shows_a_problem(staff_client, monkeypatch):
    from apps.ops import health  # noqa: PLC0415

    bad = health.Check("redis", "Redis", health.FAIL, "Cannot connect", "refused")
    monkeypatch.setattr(health, "run_all", lambda **_kw: [("Services", [bad])])

    page = staff_client.get(reverse("ops:overview")).content.decode()

    assert "Cannot connect" in page
    assert "Problem" in page


# Runs


def test_the_run_list_filters(staff_client, boss):
    TaskRun.objects.create(task_id="a", task_name="x", label="alpha", status="success")
    TaskRun.objects.create(task_id="b", task_name="x", label="beta", status="failure")
    TaskRun.objects.create(
        task_id="c", task_name="x", label="gamma", trigger="manual", triggered_by=boss
    )
    url = reverse("ops:runs")

    def labels(**params):
        response = staff_client.get(url, params)
        return sorted(r.label for r in response.context["page"])

    assert labels() == ["alpha", "beta", "gamma"]
    assert labels(status="failure") == ["beta"]
    assert labels(label="alpha") == ["alpha"]
    assert labels(trigger="manual") == ["gamma"]
    assert labels(status="nonsense") == ["alpha", "beta", "gamma"]


def test_the_run_page_shows_the_error_and_the_output(staff_client):
    run = TaskRun.objects.create(
        task_id="e1",
        task_name="x",
        label="command: llm_check",
        status="failure",
        error="Traceback ... ValueError: broken thing",
        output="Server answered in 40 ms",
    )

    page = staff_client.get(reverse("ops:run", args=[run.pk])).content.decode()
    partial = staff_client.get(reverse("ops:run", args=[run.pk]), headers=DS).content.decode()

    assert "ValueError: broken thing" in page
    assert "Server answered in 40 ms" in page
    assert "<html" not in partial
    assert "ValueError: broken thing" in partial


def test_the_run_page_escapes_the_output(staff_client):
    run = TaskRun.objects.create(
        task_id="x1", task_name="x", label="x", output="<script>alert(1)</script>"
    )

    page = staff_client.get(reverse("ops:run", args=[run.pk])).content.decode()

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_a_missing_run_is_a_404(staff_client):
    assert staff_client.get(reverse("ops:run", args=[999])).status_code == 404


def test_the_jobs_page_shows_the_last_run_and_the_next_run(staff_client, offline):
    TaskRun.objects.create(task_id="p1", task_name="ops.prune", label="ops.prune", status="success")

    page = staff_client.get(reverse("ops:jobs")).content.decode()

    assert "Clean old history" in page
    assert "40 3 * * *" in page


# Logs


def test_the_log_page_filters_and_gives_a_partial(staff_client, tmp_path, settings):
    path = tmp_path / "app.log"
    path.write_text(
        "2026-10-07 07:00:01,100 INFO a.b: all good\n2026-10-07 07:00:02,200 ERROR a.b: it broke\n"
    )
    settings.LOG_FILE = path

    page = staff_client.get(reverse("ops:logs"), {"level": "ERROR"}).content.decode()
    partial = staff_client.get(reverse("ops:logs"), {"q": "good"}, headers=DS).content.decode()

    assert "it broke" in page
    assert "all good" not in page
    assert "<html" not in partial
    assert "all good" in partial


def test_the_log_page_works_without_a_file(staff_client, tmp_path, settings):
    settings.LOG_FILE = tmp_path / "missing.log"

    response = staff_client.get(reverse("ops:logs"))

    assert response.status_code == 200
    assert "There is no log file yet" in response.content.decode()


def test_the_log_page_accepts_datastar_signals(staff_client, tmp_path, settings):
    path = tmp_path / "app.log"
    path.write_text("2026-10-07 07:00:01,100 INFO a.b: hello world\n")
    settings.LOG_FILE = path
    signals = '{"level":"","logger":"","q":"hello","limit":"10","live":true}'

    response = staff_client.get(reverse("ops:logs"), {"datastar": signals}, headers=DS)

    assert "hello world" in response.content.decode()


def test_a_bad_datastar_value_does_not_break_the_page(staff_client, offline):
    response = staff_client.get(reverse("ops:logs"), {"datastar": "{not json", "limit": "abc"})

    assert response.status_code == 200


# Users


def test_the_user_list_search(staff_client, member, offline):
    page = staff_client.get(reverse("ops:users"), {"q": "memb"}).content.decode()

    assert "member@example.com" in page
    assert "staff@example.com" not in page


def test_the_user_page_shows_the_logins_and_the_sessions(staff_client, member, offline):
    client = Client()
    client.post(
        "/login/",
        {"username": "member", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.77"},
    )

    page = staff_client.get(reverse("ops:user", args=[member.pk])).content.decode()

    assert "203.0.113.77" in page


def test_a_superuser_ends_the_sessions_of_a_user(boss_client, boss, member):
    victim = Client()
    victim.post("/login/", {"username": "member", "password": PASSWORD})
    assert victim.get(reverse("web:dashboard")).status_code == 200

    response = boss_client.post(reverse("ops:user_end_sessions", args=[member.pk]))

    assert response.status_code == 302
    assert victim.get(reverse("web:dashboard")).status_code == 302
    event = AuditEvent.objects.get(action="end sessions")
    assert event.actor == boss
    assert event.target == "member"


def test_a_staff_user_cannot_end_sessions(staff_client, member):
    victim = Client()
    victim.post("/login/", {"username": "member", "password": PASSWORD})

    response = staff_client.post(reverse("ops:user_end_sessions", args=[member.pk]))

    assert response.status_code == 403
    assert victim.get(reverse("web:dashboard")).status_code == 200


def test_one_session_can_be_ended_by_key(boss_client, member):
    first, second = Client(), Client()
    for client in (first, second):
        client.post("/login/", {"username": "member", "password": PASSWORD})

    boss_client.post(
        reverse("ops:user_end_sessions", args=[member.pk]), {"key": first.session.session_key}
    )

    assert first.get(reverse("web:dashboard")).status_code == 302
    assert second.get(reverse("web:dashboard")).status_code == 200


def test_a_key_of_another_user_is_not_ended(boss_client, member, staff):
    other = Client()
    other.post("/login/", {"username": "staff", "password": PASSWORD})

    response = boss_client.post(
        reverse("ops:user_end_sessions", args=[member.pk]), {"key": other.session.session_key}
    )

    assert response.status_code == 404
    assert Session.objects.filter(session_key=other.session.session_key).exists()


def test_a_superuser_turns_a_user_off_and_on(boss_client, member):
    url = reverse("ops:user_set_active", args=[member.pk])

    boss_client.post(url, {"active": "no"})
    member.refresh_from_db()
    assert not member.is_active

    boss_client.post(url, {"active": "yes"})
    member.refresh_from_db()
    assert member.is_active
    assert list(AuditEvent.objects.values_list("action", flat=True)) == [
        "turn on user",
        "turn off user",
    ]


def test_a_user_that_is_off_cannot_log_in(boss_client, member):
    boss_client.post(reverse("ops:user_set_active", args=[member.pk]), {"active": "no"})

    response = Client().post("/login/", {"username": "member", "password": PASSWORD})

    assert response.status_code == 200  # The form again.
    assert LoginEvent.objects.filter(kind=LoginEvent.Kind.FAILED, username="member").exists()


def test_an_admin_cannot_turn_off_the_own_account_on_the_page(boss_client, boss):
    response = boss_client.post(
        reverse("ops:user_set_active", args=[boss.pk]), {"active": "no"}, follow=True
    )

    boss.refresh_from_db()
    assert boss.is_active
    assert "cannot turn off your own account" in response.content.decode()


def test_a_staff_user_cannot_turn_a_user_off(staff_client, member):
    assert (
        staff_client.post(reverse("ops:user_set_active", args=[member.pk]), {"active": "no"})
    ).status_code == 403
    member.refresh_from_db()
    assert member.is_active


def test_the_actions_need_post(boss_client, member):
    assert boss_client.get(reverse("ops:user_set_active", args=[member.pk])).status_code == 405
    assert boss_client.get(reverse("ops:user_end_sessions", args=[member.pk])).status_code == 405


def test_the_actions_need_the_csrf_token(boss, member):
    client = Client(enforce_csrf_checks=True)
    client.force_login(boss)

    response = client.post(reverse("ops:user_set_active", args=[member.pk]), {"active": "no"})

    assert response.status_code == 403
    member.refresh_from_db()
    assert member.is_active


# Logins and audit


def test_the_login_list_filters(staff_client):
    Client().post("/login/", {"username": "nobody", "password": "x"})

    page = staff_client.get(reverse("ops:logins"), {"kind": "failed"}).content.decode()
    other = staff_client.get(reverse("ops:logins"), {"kind": "logout"}).content.decode()

    assert "nobody" in page
    assert "nobody" not in other


def test_a_bad_hours_value_is_ignored(staff_client):
    assert staff_client.get(reverse("ops:logins"), {"hours": "abc"}).status_code == 200


def test_the_audit_page_lists_the_actions(staff_client, boss):
    audit.record(boss, "run job", "news.fetch_feeds", "from a test")

    page = staff_client.get(reverse("ops:audit")).content.decode()

    assert "run job" in page
    assert "news.fetch_feeds" in page
    assert "boss" in page


def test_the_audit_record_has_the_client_address(boss, rf):
    request = rf.post("/x", headers={"X-Forwarded-For": "198.51.100.4"})

    event = audit.record(boss, "a", request=request)

    assert event.ip_address == "198.51.100.4"


# Config


def test_the_config_page_hides_the_secrets(settings, staff):
    settings.TELEGRAM_BOT_TOKEN = "987654:VERY-SECRET-BOT-TOKEN-VALUE"
    settings.SECRET_KEY = "django-secret-key-for-this-test-only"
    staff_client = Client()  # Log in after the key change. The session uses the key.
    staff_client.force_login(staff)

    page = staff_client.get(reverse("ops:config")).content.decode()

    assert "VERY-SECRET-BOT-TOKEN-VALUE" not in page
    assert "TELEGRAM_BOT_TOKEN" in page
    assert "django-secret-key-for-this-test-only" not in page


# Metrics


def test_the_metrics_page_works_without_redis_and_workers(staff_client):
    """This is the case that matters most: the admin opens the page because something is down."""
    response = staff_client.get(reverse("ops:metrics"))

    assert response.status_code == 200
    page = response.content.decode()
    assert "Task runs" in page
