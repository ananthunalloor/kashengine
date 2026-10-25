"""Actions that change the feature blocks and the subscriptions.

All actions write a history row (`SubscriptionEvent`) so an admin can see what happened.
The pages that call these functions also write the audit trail.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.siteconfig import conf

from . import features
from .models import FeatureBlock, Subscription, SubscriptionEvent

MAX_DAYS = 3650


def _event(user, action: str, sub: Subscription, actor, note: str) -> None:
    """Write one history row (`SubscriptionEvent`) for a change of a subscription.

    Args:
        user: The owner of the subscription.
        action: A value of `SubscriptionEvent.Action`.
        sub: The subscription after the change. Its kind and end time go in the row.
        actor: The admin who made the change, or None for a change by the system.
        note: A free text. The function cuts it to 200 characters.
    """
    SubscriptionEvent.objects.create(
        user=user,
        action=action,
        kind=sub.kind,
        ends_at=sub.ends_at,
        note=note[:200],
        actor=actor,
        actor_name=actor.get_username() if actor else "",
    )


def end_of_day(day: date) -> datetime:
    """Return the last moment of a day in the local time zone (IST).

    Args:
        day: The calendar date.

    Returns:
        23:59:59 of that date in `settings.TIME_ZONE`, as a UTC datetime.
    """
    zone = ZoneInfo(settings.TIME_ZONE)
    return datetime.combine(day, time(23, 59, 59), tzinfo=zone).astimezone(UTC)


@transaction.atomic
def start_trial(user, now: datetime | None = None) -> Subscription:
    """Give a new user the trial. Do nothing if the user has a subscription row already.

    The trial has the length `SUBSCRIPTION_TRIAL_DAYS`. The function writes one history row.

    Args:
        user: The new user.
        now: The start time. The default is the current time.

    Returns:
        The new trial, or the subscription that the user already had.
    """
    now = now or timezone.now()
    existing = Subscription.objects.filter(user=user).first()
    if existing:
        return existing
    sub = Subscription.objects.create(
        user=user,
        kind=Subscription.Kind.TRIAL,
        started_at=now,
        ends_at=now + timedelta(days=int(conf.SUBSCRIPTION_TRIAL_DAYS)),
    )
    _event(user, SubscriptionEvent.Action.STARTED, sub, None, "Trial for a new user")
    return sub


@transaction.atomic
def give(
    user,
    kind: str,
    *,
    days: int | None = None,
    ends_on: date | None = None,
    actor=None,
    note: str = "",
    now: datetime | None = None,
) -> Subscription:
    """Give or change the subscription of a user. Raise ValueError if the input is not valid.

    With `days`, the days are added to the end of the current subscription (or to now, if it has
    ended). With `ends_on`, the subscription ends at the end of that day. Use one of them.

    Args:
        user: The owner of the subscription.
        kind: One of `trial`, `paid` or `gift`.
        days: The days to add, from 1 to 3650.
        ends_on: The last day of the subscription, in the local time zone. It must be in the
            future.
        actor: The admin who gives the subscription, or None.
        note: A free text for the history. The history keeps 200 characters.
        now: The current time. Tests set it.

    Returns:
        The saved subscription.

    Raises:
        ValueError: If `kind` is not known, if both or none of `days` and `ends_on` are set,
            if `days` is out of range, or if `ends_on` is not in the future.

    Note:
        A subscription that never ends (no end time) counts as ended for the `days` rule. The
        new end is `days` after now.
    """
    now = now or timezone.now()
    if kind not in Subscription.Kind.values:
        msg = "Choose a kind: trial, paid, or gift."
        raise ValueError(msg)
    if (days is None) == (ends_on is None):
        msg = "Enter the number of days, or an end date. Not both."
        raise ValueError(msg)
    sub = Subscription.objects.select_for_update().filter(user=user).first()
    if days is not None:
        if not 1 <= days <= MAX_DAYS:
            msg = f"Days must be from 1 to {MAX_DAYS}."
            raise ValueError(msg)
        base = sub.ends_at if sub and sub.ends_at and sub.ends_at > now else now
        ends_at = base + timedelta(days=days)
    else:
        ends_at = end_of_day(cast("date", ends_on))
        if ends_at <= now:
            msg = "The end date must be in the future. To stop the subscription, end it."
            raise ValueError(msg)
    if sub is None:
        sub = Subscription(user=user, started_at=now)
    elif not sub.is_active(now):
        sub.started_at = now  # A new period starts after an ended one.
    sub.kind, sub.ends_at = kind, ends_at
    sub.save()
    _event(user, SubscriptionEvent.Action.GIVEN, sub, actor, note)
    return sub


@transaction.atomic
def end_now(user, *, actor=None, note: str = "", now: datetime | None = None) -> Subscription:
    """End the subscription now. Raise ValueError if the user has none.

    Args:
        user: The owner of the subscription.
        actor: The admin who ends it, or None.
        note: A free text for the history.
        now: The end time. The default is the current time.

    Returns:
        The saved subscription. Its end time is `now`.

    Raises:
        ValueError: If the user has no subscription.
    """
    now = now or timezone.now()
    sub = Subscription.objects.select_for_update().filter(user=user).first()
    if sub is None:
        msg = "This user has no subscription."
        raise ValueError(msg)
    sub.ends_at = now
    sub.save()
    _event(user, SubscriptionEvent.Action.ENDED, sub, actor, note)
    return sub


@transaction.atomic
def set_blocked(user, blocked: Iterable[str], *, actor=None) -> tuple[list[str], list[str]]:
    """Make the blocked features of a user equal to `blocked`.

    The function adds the missing blocks and deletes the blocks that are not in `blocked`.

    Args:
        user: The user.
        blocked: The keys of all features that the user must not use after the call.
        actor: The admin who makes the change. The new blocks keep the name.

    Returns:
        Two sorted lists: the features that are blocked now, and the features that are allowed
        again.

    Raises:
        ValueError: If a key is not a known feature. The database does not change.
    """
    wanted = set(blocked)
    unknown = wanted - features.KEYS
    if unknown:
        msg = f"Unknown feature: {', '.join(sorted(unknown))}."
        raise ValueError(msg)
    current = set(FeatureBlock.objects.filter(user=user).values_list("feature", flat=True))
    added, removed = sorted(wanted - current), sorted(current - wanted)
    FeatureBlock.objects.bulk_create(
        FeatureBlock(user=user, feature=key, created_by=actor) for key in added
    )
    FeatureBlock.objects.filter(user=user, feature__in=removed).delete()
    return added, removed
