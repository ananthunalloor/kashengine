"""The API token model.

A token is a secret that a user makes on the Account page. The secret is shown once. The
database keeps only a SHA-256 hash of it, so a database leak does not give working tokens.
"""

from datetime import datetime
from typing import ClassVar, Literal

from django.conf import settings
from django.db import models
from django.utils import timezone

TOKEN_PREFIX = "ke"  # noqa: S105 - the fixed start of every token, not a secret.


class ApiToken(models.Model):
    """One API token of one user.

    The full token has the form `ke_<prefix>_<secret>`. The prefix is stored in plain text
    (it is not secret). It lets the user tell tokens apart and lets the server find the row
    without scanning all hashes. The secret part is never stored.

    Attributes:
        user: The owner. The token has the access of this user, never more.
        name: A label that the user chose, for example "Excel sheet".
        prefix: Eight hex characters. Unique. Shown in lists as `ke_<prefix>_...`.
        token_hash: The SHA-256 hash (hex) of the full token.
        password_stamp: A short fingerprint of the password hash at the time of creation. When
            the password changes, the stamp no longer matches and the token stops working.
        created_at: When the token was made.
        last_used_at: When the token was last used. It is updated at most once a minute.
        expires_at: When the token ends. Empty means it does not expire.
        revoked_at: When the token was revoked. Empty means it was not.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens"
    )
    name = models.CharField(max_length=60)
    prefix = models.CharField(max_length=8, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    password_stamp = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return the prefix and the name. The text has no secret."""
        return f"{TOKEN_PREFIX}_{self.prefix}_... ({self.name})"

    @property
    def display(self) -> str:
        """The token as it is shown in lists: the prefix and no secret."""
        return f"{TOKEN_PREFIX}_{self.prefix}_…"

    def is_expired(self, now: datetime | None = None) -> bool:
        """True if the token has an end date that is in the past.

        Args:
            now: The time to compare with. The default is the current time.

        Returns:
            True if `expires_at` is set and is not later than `now`. A token without an end date
            never expires.
        """
        return self.expires_at is not None and self.expires_at <= (now or timezone.now())

    def is_active(self, now: datetime | None = None) -> bool:
        """True if the token is not revoked and not expired.

        Args:
            now: The time to compare with. The default is the current time.

        Returns:
            True if the token can be used at `now`.
        """
        return self.revoked_at is None and not self.is_expired(now)

    @property
    def state(self) -> Literal["active", "expired", "revoked"]:
        """`active`, `expired` or `revoked`. A revoked token is `revoked` even if it also ended."""
        if self.revoked_at is not None:
            return "revoked"
        return "expired" if self.is_expired() else "active"
