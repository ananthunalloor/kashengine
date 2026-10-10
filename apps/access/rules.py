"""Who may use what. One `Access` object answers all questions about one user.

Order of the rules:

1. Staff and superusers have all features. A subscription is not needed.
2. If "Require a subscription" is on, a user needs an active trial or subscription. Without it,
   the user has no feature.
3. A feature that an admin removed (a FeatureBlock) is not allowed.
4. Everything else is allowed.
"""

from datetime import datetime
from functools import cached_property
from typing import cast

from django.utils import timezone

from apps.siteconfig import conf

from . import features
from .models import Subscription

_LOAD = object()  # Means: read the subscription from the database.


def is_exempt(user) -> bool:
    """Staff and superusers are never blocked."""
    return bool(user.is_staff or user.is_superuser)


class Access:
    """The access of one user at one moment. It reads the database at most twice."""

    def __init__(self, user, now: datetime | None = None, *, subscription=_LOAD) -> None:
        """Pass `subscription` (a row or None) if you already have it. This saves a query."""
        self.user = user
        self.now = now or timezone.now()
        if subscription is not _LOAD:
            self.subscription = cast("Subscription | None", subscription)

    @property
    def authenticated(self) -> bool:
        """False for an anonymous visitor."""
        return bool(getattr(self.user, "is_authenticated", False))

    @property
    def exempt(self) -> bool:
        """True for staff and superusers."""
        return self.authenticated and is_exempt(self.user)

    @cached_property
    def subscription(self) -> Subscription | None:
        """The subscription of the user, or None."""
        if not self.authenticated:
            return None
        return Subscription.objects.filter(user=self.user).first()

    @cached_property
    def blocked(self) -> frozenset[str]:
        """The features that an admin removed from this user."""
        if not self.authenticated or self.exempt:
            return frozenset()
        keys = self.user.feature_blocks.values_list("feature", flat=True)
        return frozenset(keys) & features.KEYS

    @property
    def subscription_ok(self) -> bool:
        """True if the user may use the site now (the subscription rule)."""
        if not self.authenticated:
            return False
        if self.exempt or not conf.SUBSCRIPTIONS_REQUIRED:
            return True
        return self.subscription is not None and self.subscription.is_active(self.now)

    @cached_property
    def allowed(self) -> frozenset[str]:
        """The keys of the features the user may use now."""
        if not self.authenticated:
            return frozenset()
        if self.exempt:
            return features.KEYS
        if not self.subscription_ok:
            return frozenset()
        return features.KEYS - self.blocked

    def can(self, feature: str) -> bool:
        """True if the user may use the feature."""
        return feature in self.allowed

    @property
    def state(self) -> str:
        """trial, active, expired, none, or staff. This is what the account page shows."""
        if self.exempt:
            return "staff"
        sub = self.subscription
        if sub is None:
            return "none"
        if not sub.is_active(self.now):
            return "expired"
        return "trial" if sub.kind == Subscription.Kind.TRIAL else "active"

    def notice(self) -> str:
        """A short text for the menu: a locked user, or an end that is near. Empty if none."""
        if self.exempt or not conf.SUBSCRIPTIONS_REQUIRED or not self.authenticated:
            return ""
        if not self.subscription_ok:
            return "Your access has ended."
        sub = self.subscription
        left = sub.days_left(self.now) if sub else None
        if left is None or left > conf.SUBSCRIPTION_NOTICE_DAYS:
            return ""
        what = "trial" if sub and sub.kind == Subscription.Kind.TRIAL else "subscription"
        when = "today" if left <= 1 else f"in {left} days"
        return f"Your {what} ends {when}."
