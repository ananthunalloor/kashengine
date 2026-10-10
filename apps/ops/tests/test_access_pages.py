"""The Ops pages for feature permissions and subscriptions."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.access import service
from apps.access.models import FeatureBlock, Subscription, SubscriptionEvent
from apps.ops.models import AuditEvent
from apps.siteconfig import conf
from apps.siteconfig import service as site_service

pytestmark = pytest.mark.django_db

ALL_KEYS = ["reports", "news", "ipos", "markets", "companies", "delivery"]


def _user_url(user, name="ops:user"):
    return reverse(name, args=[user.pk])


def _allow_all_except(*blocked):
    return {"allow": [key for key in ALL_KEYS if key not in blocked]}


# Access to the pages


def test_the_subscription_page_follows_the_access_rules(
    client, member_client, staff_client, boss_client, offline
):
    url = reverse("ops:subscriptions")

    assert client.get(url).status_code == 302
    assert member_client.get(url).status_code == 403
    assert staff_client.get(url).status_code == 200
    assert boss_client.get(url).status_code == 200


def test_the_ops_menu_has_the_subscription_link(boss_client, offline):
    page = boss_client.get(reverse("ops:overview")).content.decode()

    assert f'href="{reverse("ops:subscriptions")}"' in page


def test_every_change_needs_a_superuser(staff_client, member):
    posts = [
        (_user_url(member, "ops:user_access"), _allow_all_except("news")),
        (_user_url(member, "ops:user_subscription_give"), {"kind": "paid", "days": "30"}),
        (_user_url(member, "ops:user_subscription_end"), {}),
    ]

    for url, data in posts:
        assert staff_client.post(url, data).status_code == 403

    assert not FeatureBlock.objects.exists()
    assert member.subscription.kind == "trial"


def test_a_normal_user_cannot_change_anything(member_client, boss):
    url = _user_url(boss, "ops:user_access")

    assert member_client.post(url, _allow_all_except("news")).status_code == 403


def test_the_change_pages_need_a_post(boss_client, member):
    for name in ("ops:user_access", "ops:user_subscription_give", "ops:user_subscription_end"):
        assert boss_client.get(_user_url(member, name)).status_code == 405


def test_an_unknown_user_is_a_404(boss_client):
    assert boss_client.post(reverse("ops:user_access", args=[999999])).status_code == 404


# The user page


def test_the_user_page_shows_the_boxes_for_a_superuser(boss_client, member, offline):
    page = boss_client.get(_user_url(member)).content.decode()

    for key in ALL_KEYS:
        assert f'value="{key}"' in page
    assert page.count("checked") >= len(ALL_KEYS)
    assert "Give or change the subscription" in page
    assert "Trial" in page


def test_a_removed_feature_has_no_tick(boss_client, member, offline):
    service.set_blocked(member, {"ipos"})

    page = boss_client.get(_user_url(member)).content.decode()

    assert 'value="ipos" class="mt-1 h-4 w-4 rounded border-rule" checked' not in page
    assert 'value="news" class="mt-1 h-4 w-4 rounded border-rule" checked' in page


def test_a_staff_user_sees_the_state_but_has_no_forms(staff_client, member, offline):
    page = staff_client.get(_user_url(member)).content.decode()

    assert "Features" in page
    assert reverse("ops:user_access", args=[member.pk]) not in page
    assert "Give or change the subscription" not in page


def test_the_page_of_a_staff_user_says_that_staff_have_everything(boss_client, staff, offline):
    page = boss_client.get(_user_url(staff)).content.decode()

    assert "Staff have all features always" in page
    assert "Staff account" in page


# Features


def test_a_superuser_removes_a_feature(boss_client, member):
    response = boss_client.post(_user_url(member, "ops:user_access"), _allow_all_except("ipos"))

    assert response.status_code == 302
    assert set(FeatureBlock.objects.values_list("feature", flat=True)) == {"ipos"}
    event = AuditEvent.objects.get(action="change access")
    assert event.target == "member"
    assert "removed: ipos" in event.detail


def test_a_superuser_gives_a_feature_back(boss_client, member):
    service.set_blocked(member, {"ipos", "news"})

    boss_client.post(_user_url(member, "ops:user_access"), _allow_all_except("news"))

    assert set(FeatureBlock.objects.values_list("feature", flat=True)) == {"news"}
    assert "given back: ipos" in AuditEvent.objects.get(action="change access").detail


def test_saving_without_a_change_writes_no_audit_event(boss_client, member):
    boss_client.post(_user_url(member, "ops:user_access"), _allow_all_except())

    assert not AuditEvent.objects.filter(action="change access").exists()


def test_an_unknown_feature_in_the_form_is_ignored_safely(boss_client, member):
    data = {"allow": [*ALL_KEYS, "nonsense"]}

    boss_client.post(_user_url(member, "ops:user_access"), data)

    assert not FeatureBlock.objects.exists()


def test_the_change_applies_to_the_right_user_only(boss_client, member, django_user_model):
    other = django_user_model.objects.create_user("other")

    boss_client.post(_user_url(member, "ops:user_access"), _allow_all_except("news"))

    assert FeatureBlock.objects.filter(user=member).count() == 1
    assert not FeatureBlock.objects.filter(user=other).exists()


# Subscriptions


def test_a_superuser_gives_days(boss_client, member):
    before = member.subscription.ends_at

    response = boss_client.post(
        _user_url(member, "ops:user_subscription_give"),
        {"kind": "paid", "days": "30", "note": "UPI 99"},
    )

    member.subscription.refresh_from_db()
    assert response.status_code == 302
    assert member.subscription.kind == "paid"
    assert member.subscription.ends_at == before + timedelta(days=30)
    event = SubscriptionEvent.objects.filter(action="given").get()
    assert (event.actor_name, event.note) == ("boss", "UPI 99")
    audit = AuditEvent.objects.get(action="give subscription")
    assert "paid" in audit.detail
    assert "UPI 99" in audit.detail


def test_a_superuser_sets_an_end_date(boss_client, member):
    day = (timezone.now() + timedelta(days=40)).date().isoformat()

    boss_client.post(
        _user_url(member, "ops:user_subscription_give"), {"kind": "gift", "ends_on": day}
    )

    member.subscription.refresh_from_db()
    assert member.subscription.kind == "gift"
    assert member.subscription.ends_at > timezone.now() + timedelta(days=38)


@pytest.mark.parametrize(
    "data",
    [
        {"kind": "paid"},  # No days and no date.
        {"kind": "paid", "days": "5", "ends_on": "2999-01-01"},  # Both.
        {"kind": "paid", "days": "0"},
        {"kind": "paid", "days": "99999"},
        {"kind": "free", "days": "5"},
        {"kind": "paid", "ends_on": "2001-01-01"},  # In the past.
        {"kind": "paid", "ends_on": "not a date"},
    ],
)
def test_bad_input_is_refused_with_a_message(boss_client, member, data):
    before = member.subscription.ends_at

    response = boss_client.post(_user_url(member, "ops:user_subscription_give"), data, follow=True)

    member.subscription.refresh_from_db()
    assert member.subscription.ends_at == before
    assert "Not saved" in response.content.decode()
    assert not AuditEvent.objects.filter(action="give subscription").exists()


def test_a_superuser_ends_the_subscription(boss_client, member):
    response = boss_client.post(_user_url(member, "ops:user_subscription_end"))

    member.subscription.refresh_from_db()
    assert response.status_code == 302
    assert not member.subscription.is_active()
    assert AuditEvent.objects.filter(action="end subscription", target="member").exists()
    assert SubscriptionEvent.objects.filter(action="ended").exists()


def test_ending_for_a_user_without_a_subscription_says_so(boss_client, member):
    Subscription.objects.filter(user=member).delete()

    response = boss_client.post(_user_url(member, "ops:user_subscription_end"), follow=True)

    assert "no subscription" in response.content.decode()


def test_the_history_shows_on_the_user_page(boss_client, member, offline):
    service.give(member, "paid", days=30, actor=member, note="first payment")

    page = boss_client.get(_user_url(member)).content.decode()

    assert "Trial started" in page
    assert "first payment" in page


def test_the_login_list_and_the_subscription_history_do_not_mix(boss_client, member, offline):
    from apps.ops.models import LoginEvent  # noqa: PLC0415

    LoginEvent.objects.create(
        user=member, username="member", kind=LoginEvent.Kind.LOGIN, ip_address="203.0.113.9"
    )

    page = boss_client.get(_user_url(member))

    assert "203.0.113.9" in page.content.decode()  # In "Recent logins".
    assert [e.kind for e in page.context["events"]] == ["login"]
    assert [e.action for e in page.context["sub_events"]] == ["started"]


def test_the_end_button_shows_only_for_a_running_subscription(boss_client, member, offline):
    end_url = reverse("ops:user_subscription_end", args=[member.pk])
    assert end_url in boss_client.get(_user_url(member)).content.decode()

    service.end_now(member)

    assert end_url not in boss_client.get(_user_url(member)).content.decode()


def test_the_page_says_if_the_lock_rule_is_on(boss_client, member, offline):
    assert "is OFF" in boss_client.get(_user_url(member)).content.decode()

    site_service.save({"SUBSCRIPTIONS_REQUIRED": True})

    assert "is ON" in boss_client.get(_user_url(member)).content.decode()


# The lists


def test_the_users_list_shows_the_subscription_and_removed_features(
    boss_client, member, offline, django_assert_max_num_queries
):
    service.set_blocked(member, {"ipos", "news"})
    service.give(member, "paid", days=30)

    page = boss_client.get(reverse("ops:users")).content.decode()

    assert "2 removed" in page
    assert "Paid" in page


def test_the_users_list_does_not_query_for_each_user(boss_client, offline, django_user_model):
    from django.db import connection  # noqa: PLC0415
    from django.test.utils import CaptureQueriesContext  # noqa: PLC0415

    def count():
        with CaptureQueriesContext(connection) as ctx:
            boss_client.get(reverse("ops:users"))
        return len(ctx)

    base = count()
    for number in range(8):
        django_user_model.objects.create_user(f"extra{number}")

    assert count() == base


def test_the_subscription_list_counts_and_filters(
    boss_client, member, staff, django_user_model, expire, offline
):
    paid = django_user_model.objects.create_user("payer")
    service.give(paid, "paid", days=30)
    gone = django_user_model.objects.create_user("gone")
    expire(gone)
    nobody = django_user_model.objects.create_user("nobody")
    Subscription.objects.filter(user=nobody).delete()
    url = reverse("ops:subscriptions")

    def names(state=""):
        response = boss_client.get(url, {"state": state} if state else {})
        return sorted(row["user"].username for row in response.context["rows"])

    assert names("trial") == ["member"]
    assert names("active") == ["payer"]
    assert names("expired") == ["gone"]
    assert names("none") == ["nobody"]
    assert "staff" in names("staff")
    assert "member" in names()
    assert names("nonsense") == names()
    counts = {key: count for key, _label, count in boss_client.get(url).context["counts"]}
    assert counts["trial"] == 1
    assert counts["active"] == 1


def test_the_subscription_list_for_staff(staff_client, member, offline):
    page = staff_client.get(reverse("ops:subscriptions")).content.decode()

    assert "member" in page


# The settings group


def test_the_subscription_settings_page_saves_the_values(boss_client):
    url = reverse("ops:settings_group", args=["subscription"])
    values = {
        "SUBSCRIPTIONS_REQUIRED": "on",
        "SUBSCRIPTION_TRIAL_DAYS": "10",
        "SUBSCRIPTION_PERIOD_DAYS": "31",
        "SUBSCRIPTION_PRICE": "249.5",
        "SUBSCRIPTION_CURRENCY": "INR",
        "SUBSCRIPTION_NOTICE_DAYS": "5",
        "SUBSCRIPTION_CONTACT_TEXT": "Message the admin.",
    }

    response = boss_client.post(url, values)

    assert response.status_code == 302
    assert conf.SUBSCRIPTIONS_REQUIRED is True
    assert conf.SUBSCRIPTION_TRIAL_DAYS == 10
    assert conf.SUBSCRIPTION_PRICE == 249.5
    assert AuditEvent.objects.filter(action="change settings", target="Subscription").exists()


def test_a_bad_trial_length_is_refused(boss_client):
    url = reverse("ops:settings_group", args=["subscription"])
    values = {
        "SUBSCRIPTION_TRIAL_DAYS": "-1",
        "SUBSCRIPTION_PERIOD_DAYS": "30",
        "SUBSCRIPTION_PRICE": "0",
        "SUBSCRIPTION_CURRENCY": "INR",
        "SUBSCRIPTION_NOTICE_DAYS": "3",
        "SUBSCRIPTION_CONTACT_TEXT": "x",
    }

    response = boss_client.post(url, values)

    assert response.status_code == 200
    assert not conf.is_saved("SUBSCRIPTION_TRIAL_DAYS")
