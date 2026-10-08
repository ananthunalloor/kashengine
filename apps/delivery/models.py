"""Models for the delivery log."""

from typing import ClassVar

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
    recipient = models.CharField(max_length=200, blank=True, help_text="Chat ID or email address.")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.status} {self.created_at:%Y-%m-%d %H:%M}"
