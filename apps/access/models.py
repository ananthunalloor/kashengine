"""Database tables for the feature blocks and the subscriptions."""

import math
from datetime import datetime
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

SECONDS_PER_DAY = 86400


class FeatureBlock(models.Model):
    """A feature that an admin removed from one user. No row means: the user has the feature."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feature_blocks"
    )
    feature = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering: ClassVar[list[str]] = ["user_id", "feature"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["user", "feature"], name="one_block_per_feature")
        ]

    def __str__(self) -> str:
        return f"{self.user} without {self.feature}"


class Subscription(models.Model):
    """The current subscription of a user. A new user gets a trial.

    The state follows from the end time. There is no payment step yet: an admin gives the
    subscription. `ends_at` empty means: it does not end (an admin can still end it).
    """

    class Kind(models.TextChoices):
        TRIAL = "trial", "Trial"
        PAID = "paid", "Paid"
        GIFT = "gift", "Gift from an admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TRIAL)
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user}: {self.kind}"

    def is_active(self, now: datetime | None = None) -> bool:
        """True if the subscription has not ended."""
        now = now or timezone.now()
        return self.ends_at is None or self.ends_at > now

    def days_left(self, now: datetime | None = None) -> int | None:
        """Whole days until the end (rounded up). None if it does not end. 0 if it ended."""
        if self.ends_at is None:
            return None
        now = now or timezone.now()
        seconds = (self.ends_at - now).total_seconds()
        return math.ceil(seconds / SECONDS_PER_DAY) if seconds > 0 else 0


class SubscriptionEvent(models.Model):
    """One change of a subscription. This is the history of the user."""

    class Action(models.TextChoices):
        STARTED = "started", "Trial started"
        GIVEN = "given", "Given"
        ENDED = "ended", "Ended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_events"
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    kind = models.CharField(max_length=10, choices=Subscription.Kind.choices)
    ends_at = models.DateTimeField(
        null=True, blank=True, help_text="The end time after the change."
    )
    note = models.CharField(max_length=200, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_name = models.CharField(
        max_length=150, blank=True, help_text="Kept if the user is deleted."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.user}: {self.action}"
