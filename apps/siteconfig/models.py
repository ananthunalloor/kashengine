"""The stored settings."""

from django.conf import settings
from django.db import models


class Setting(models.Model):
    """One value that an admin set on the dashboard.

    `value` is JSON text. For a secret it is an encrypted token (see crypto.py). A key without a
    row uses the value from the environment (or the default in config/settings/base.py).
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self) -> str:
        return self.key
