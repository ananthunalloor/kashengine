"""Models for the delivery log."""

import hashlib
import secrets
from typing import ClassVar

from django.conf import settings
from django.db import models


class DeliveryLog(models.Model):
    """One try to send a report on one channel."""

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    report = models.ForeignKey(
        "reports.Report",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    recipient = models.CharField(max_length=254, blank=True, help_text="Chat ID or email address.")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.status} {self.created_at:%Y-%m-%d %H:%M}"


class DeliveryPreference(models.Model):
    """A user's verified destinations and report channel choices."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delivery_preference"
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    email_reports = models.BooleanField(default=False)
    telegram_reports = models.BooleanField(default=False)
    telegram_chat_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    def __str__(self):
        return f"Report delivery settings for {self.user}"


class EmailVerification(models.Model):
    """A short-lived, one-time verification token stored only as a digest."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_verification"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Email verification for {self.user}"


class TelegramLink(models.Model):
    """A short-lived one-time code used to link a Telegram chat through the bot."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Telegram link for {self.user}"


class SignupInvite(models.Model):
    """An administrator-issued invitation that can register exactly one account."""

    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="issued_signup_invites",
    )
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redeemed_signup_invites",
    )
    revoked = models.BooleanField(default=False)

    def __str__(self):
        return f"Sign-up invitation #{self.pk}"

    def generate_code(self) -> str:
        """Set a new invitation's digest and return the code without persisting plaintext."""
        if self.pk is not None:
            raise ValueError("An existing invitation cannot generate a new code.")
        code = secrets.token_urlsafe(32)
        self.token_hash = hashlib.sha256(code.encode()).hexdigest()
        return code


class LegalAcceptance(models.Model):
    """The version of the sign-up agreement explicitly accepted by a user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="legal_acceptance"
    )
    version = models.CharField(max_length=50)
    accepted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Legal acceptance for {self.user}: {self.version}"
