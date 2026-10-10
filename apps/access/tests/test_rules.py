"""The access rules: features, subscriptions, and the state of a user."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.access import features, service
from apps.access.models import FeatureBlock, Subscription, SubscriptionEvent
from apps.access.rules import Access
from apps.siteconfig import service as site_service

pytestmark = pytest.mark.django_db

ALL = features.KEYS


def _require(on: bool = True):
    site_service.save({"SUBSCRIPTIONS_REQUIRED": on})


# New users


def test_a_new_user_gets_a_trial_of_the_setting_days(member):
    sub = member.subscription

    assert sub.kind == Subscription.Kind.TRIAL
    days = (sub.ends_at - sub.started_at).total_seconds() / 86400
    assert days == pytest.approx(7, abs=0.01)
    event = SubscriptionEvent.objects.get(user=member)
    assert event.action == "started"


def test_the_trial_length_is_a_dashboard_setting(django_user_model):
    site_service.save({"SUBSCRIPTION_TRIAL_DAYS": 14})

    user = django_user_model.objects.create_user("later")

    days = (user.subscription.ends_at - user.subscription.started_at).days
    assert days == 14


def test_a_zero_day_trial_is_over_at_once(django_user_model):
    site_service.save({"SUBSCRIPTION_TRIAL_DAYS": 0})

    user = django_user_model.objects.create_user("nodays")

    assert not user.subscription.is_active()


def test_start_trial_does_nothing_if_there_is_a_row(member):
    before = member.subscription.ends_at

    service.start_trial(member)

    assert Subscription.objects.filter(user=member).count() == 1
    assert Subscription.objects.get(user=member).ends_at == before


# Features


def test_a_user_has_all_features_by_default(member):
    access = Access(member)

    assert access.allowed == ALL
    assert all(access.can(key) for key in ALL)


def test_a_blocked_feature_is_not_allowed_and_the_others_are(member):
    FeatureBlock.objects.create(user=member, feature="ipos")

    access = Access(member)

    assert not access.can("ipos")
    assert access.allowed == ALL - {"ipos"}


def test_an_unknown_block_is_ignored(member):
    FeatureBlock.objects.create(user=member, feature="old_feature")

    assert Access(member).allowed == ALL


def test_staff_and_superusers_have_everything_even_with_blocks(staff, boss, expire):
    _require()
    for user in (staff, boss):
        FeatureBlock.objects.create(user=user, feature="news")
        expire(user)

        access = Access(user)

        assert access.exempt
        assert access.allowed == ALL
        assert access.subscription_ok
        assert access.state == "staff"


def test_an_anonymous_visitor_has_nothing():
    from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415

    access = Access(AnonymousUser())

    assert access.allowed == frozenset()
    assert not access.subscription_ok
    assert access.notice() == ""


# The subscription rule


def test_an_ended_subscription_does_not_matter_while_the_rule_is_off(member, expire):
    expire(member)

    assert Access(member).allowed == ALL


def test_an_ended_trial_locks_the_user_when_the_rule_is_on(member, expire):
    _require()
    expire(member)

    access = Access(member)

    assert not access.subscription_ok
    assert access.allowed == frozenset()
    assert access.state == "expired"


def test_a_running_trial_keeps_access_when_the_rule_is_on(member):
    _require()

    access = Access(member)

    assert access.subscription_ok
    assert access.state == "trial"
    assert access.allowed == ALL


@pytest.mark.parametrize("kind", ["paid", "gift"])
def test_a_paid_or_gift_subscription_keeps_access(member, kind):
    _require()
    service.give(member, kind, days=30)

    access = Access(member)

    assert access.subscription_ok
    assert access.state == "active"


def test_a_gift_without_an_end_date_keeps_access(member):
    _require()
    Subscription.objects.filter(user=member).update(kind="gift", ends_at=None)

    assert Access(member).state == "active"
    assert Access(member).subscription_ok


def test_a_user_without_a_subscription_row_is_locked_when_the_rule_is_on(member):
    _require()
    Subscription.objects.filter(user=member).delete()

    access = Access(member)

    assert access.state == "none"
    assert not access.subscription_ok


def test_blocks_still_apply_with_an_active_subscription(member):
    _require()
    FeatureBlock.objects.create(user=member, feature="news")

    assert Access(member).allowed == ALL - {"news"}


def test_access_with_a_given_subscription_reads_nothing(member, django_assert_num_queries):
    sub = member.subscription

    with django_assert_num_queries(0):
        access = Access(member, subscription=sub)
        assert access.state == "trial"


def test_days_left_rounds_up_and_stops_at_zero(member):
    now = timezone.now()
    sub = member.subscription

    sub.ends_at = now + timedelta(hours=1)
    assert sub.days_left(now) == 1
    sub.ends_at = now + timedelta(days=2, hours=1)
    assert sub.days_left(now) == 3
    sub.ends_at = now - timedelta(days=1)
    assert sub.days_left(now) == 0
    sub.ends_at = None
    assert sub.days_left(now) is None


# The notice


def test_no_notice_while_the_rule_is_off(member):
    Subscription.objects.filter(user=member).update(ends_at=timezone.now() + timedelta(hours=5))

    assert Access(member).notice() == ""


def test_a_notice_near_the_end(member):
    _require()
    Subscription.objects.filter(user=member).update(
        ends_at=timezone.now() + timedelta(days=2, hours=1)
    )

    assert Access(member).notice() == "Your trial ends in 3 days."


def test_a_notice_on_the_last_day(member):
    _require()
    Subscription.objects.filter(user=member).update(
        kind="paid", ends_at=timezone.now() + timedelta(hours=3)
    )

    assert Access(member).notice() == "Your subscription ends today."


def test_no_notice_far_from_the_end(member):
    _require()

    assert Access(member).notice() == ""  # 7 days left, the notice starts at 3.


def test_the_notice_days_are_a_setting(member):
    _require()
    site_service.save({"SUBSCRIPTION_NOTICE_DAYS": 10})

    assert "ends in" in Access(member).notice()


def test_a_notice_for_a_locked_user(member, expire):
    _require()
    expire(member)

    assert Access(member).notice() == "Your access has ended."
