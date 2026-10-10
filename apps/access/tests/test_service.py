"""The actions that change subscriptions and feature blocks."""

import importlib
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access import service
from apps.access.models import FeatureBlock, Subscription, SubscriptionEvent

pytestmark = pytest.mark.django_db

IST = ZoneInfo("Asia/Kolkata")


def test_days_are_added_to_the_current_end(member):
    now = timezone.now()
    Subscription.objects.filter(user=member).update(ends_at=now + timedelta(days=5))

    sub = service.give(member, "paid", days=30, now=now)

    assert sub.ends_at == now + timedelta(days=35)
    assert sub.kind == "paid"


def test_days_are_added_to_now_if_it_ended(member):
    now = timezone.now()
    Subscription.objects.filter(user=member).update(ends_at=now - timedelta(days=9))

    sub = service.give(member, "paid", days=30, now=now)

    assert sub.ends_at == now + timedelta(days=30)
    assert sub.started_at == now  # A new period.


def test_an_end_date_means_the_end_of_that_day_in_ist(member):
    day = (timezone.now() + timedelta(days=10)).astimezone(IST).date()

    sub = service.give(member, "gift", ends_on=day)

    end = sub.ends_at.astimezone(IST)
    assert (end.date(), end.hour, end.minute) == (day, 23, 59)


def test_end_of_day_uses_the_local_zone():
    assert service.end_of_day(date(2026, 3, 1)) == datetime(2026, 3, 1, 18, 29, 59, tzinfo=UTC)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"days": 0}, "from 1 to"),
        ({"days": 100000}, "from 1 to"),
        ({}, "Not both"),
        ({"days": 5, "ends_on": date(2999, 1, 1)}, "Not both"),
        ({"ends_on": date(2001, 1, 1)}, "in the future"),
    ],
)
def test_bad_input_is_refused_and_nothing_changes(member, kwargs, message):
    before = Subscription.objects.get(user=member).ends_at
    events = SubscriptionEvent.objects.count()

    with pytest.raises(ValueError, match=message):
        service.give(member, "paid", **kwargs)

    assert Subscription.objects.get(user=member).ends_at == before
    assert SubscriptionEvent.objects.count() == events


def test_an_unknown_kind_is_refused(member):
    with pytest.raises(ValueError, match="Choose a kind"):
        service.give(member, "free", days=5)


def test_give_writes_the_history_with_the_actor_and_note(member, boss):
    service.give(member, "paid", days=30, actor=boss, note="UPI 123")

    event = SubscriptionEvent.objects.filter(user=member, action="given").get()

    assert (event.actor, event.actor_name, event.note, event.kind) == (
        boss,
        "boss",
        "UPI 123",
        "paid",
    )
    assert event.ends_at is not None


def test_give_makes_a_row_for_a_user_without_one(member):
    Subscription.objects.filter(user=member).delete()

    sub = service.give(member, "gift", days=10)

    assert Subscription.objects.get(user=member) == sub


def test_end_now_ends_it_and_writes_the_history(member, boss):
    now = timezone.now()

    sub = service.end_now(member, actor=boss, note="refund", now=now)

    assert sub.ends_at == now
    assert not sub.is_active(now + timedelta(seconds=1))
    assert SubscriptionEvent.objects.filter(user=member, action="ended", note="refund").exists()


def test_end_now_needs_a_subscription(member):
    Subscription.objects.filter(user=member).delete()

    with pytest.raises(ValueError, match="no subscription"):
        service.end_now(member)


# Feature blocks


def test_set_blocked_adds_and_removes(member, boss):
    added, removed = service.set_blocked(member, {"ipos", "news"}, actor=boss)
    assert (added, removed) == (["ipos", "news"], [])
    assert FeatureBlock.objects.get(user=member, feature="ipos").created_by == boss

    added, removed = service.set_blocked(member, {"news", "markets"})
    assert (added, removed) == (["markets"], ["ipos"])
    assert set(FeatureBlock.objects.values_list("feature", flat=True)) == {"news", "markets"}

    service.set_blocked(member, set())
    assert not FeatureBlock.objects.exists()


def test_set_blocked_without_a_change_does_nothing(member):
    service.set_blocked(member, {"ipos"})

    assert service.set_blocked(member, {"ipos"}) == ([], [])


def test_set_blocked_refuses_an_unknown_feature(member):
    with pytest.raises(ValueError, match="Unknown feature: nope"):
        service.set_blocked(member, {"ipos", "nope"})

    assert not FeatureBlock.objects.exists()


def test_a_feature_can_be_blocked_once_for_a_user(member):
    FeatureBlock.objects.create(user=member, feature="ipos")

    with pytest.raises(IntegrityError), transaction.atomic():
        FeatureBlock.objects.create(user=member, feature="ipos")


def test_blocks_of_one_user_do_not_touch_another(member, staff):
    service.set_blocked(member, {"ipos"})

    assert not FeatureBlock.objects.filter(user=staff).exists()


# The migration for the users from before


def test_existing_users_get_a_gift_that_does_not_end(member, staff):
    Subscription.objects.all().delete()
    SubscriptionEvent.objects.all().delete()
    migration = importlib.import_module("apps.access.migrations.0002_existing_users")

    migration.grandfather(django_apps, None)
    migration.grandfather(django_apps, None)  # A second run adds nothing.

    subs = Subscription.objects.all()
    assert subs.count() == 2
    assert {(s.kind, s.ends_at) for s in subs} == {("gift", None)}
    assert SubscriptionEvent.objects.count() == 2
