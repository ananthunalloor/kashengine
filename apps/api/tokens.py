"""Make, check and revoke API tokens.

Token format: `ke_<prefix>_<secret>`. The prefix is 8 hex characters. The secret is 48 hex
characters (192 bits from `secrets`). The secret has enough randomness that a plain SHA-256
hash is safe to store. A slow password hash would only make each request slower.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.siteconfig import conf

from .models import TOKEN_PREFIX, ApiToken

TOKEN_RE = re.compile(rf"^{TOKEN_PREFIX}_([0-9a-f]{{8}})_([0-9a-f]{{48}})$")
LAST_USED_STEP = timedelta(minutes=1)
MAX_NAME_CHARS = 60
MAX_PREFIX_TRIES = 5


class TokenError(Exception):
    """A token cannot be used. The `code` is the API error code that the client sees."""

    def __init__(self, code: str, message: str) -> None:
        """Save the error code and the text that is safe to show to the client."""
        super().__init__(message)
        self.code = code
        self.message = message


class TokenLimitError(Exception):
    """The user has the most active tokens that the settings allow."""


def digest(raw: str) -> str:
    """Return the SHA-256 hash (hex) of a full token.

    The database keeps this hash and not the token. A token has 192 bits of random data, so a
    fast hash without a salt is safe here.

    Args:
        raw: The full token text, `ke_<prefix>_<secret>`.

    Returns:
        The 64 hex characters of the hash.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def password_stamp(user: AbstractBaseUser) -> str:
    """Return a short fingerprint of the password hash of a user.

    A changed password gives a different fingerprint. The fingerprint is not secret, and it
    cannot be used to find the password. A token keeps the fingerprint of the time when it was
    made. If the fingerprint of the user is different later, the token is not valid.

    Args:
        user: The user.

    Returns:
        The first 16 hex characters of the SHA-256 hash of the password hash of the user.
    """
    return hashlib.sha256(user.password.encode("utf-8")).hexdigest()[:16]


def active_tokens(user: AbstractBaseUser, now: datetime | None = None) -> list[ApiToken]:
    """Return the tokens of a user that can still be used, newest first.

    Args:
        user: The owner of the tokens.
        now: The time to compare with. The default is the current time.

    Returns:
        The tokens that are not revoked and not expired. The order is from the model:
        newest first.
    """
    now = now or timezone.now()
    return [token for token in ApiToken.objects.filter(user=user) if token.is_active(now)]


def issue(
    user: AbstractBaseUser, name: str, *, now: datetime | None = None
) -> tuple[ApiToken, str]:
    """Make a new token for a user.

    The lifetime comes from the setting `API_TOKEN_EXPIRY_DAYS` (0 means no end date).

    Args:
        user: The owner of the token.
        name: A label for the token. Spaces at the ends are removed. It is cut to 60 characters.
        now: The current time. Tests set it.

    Returns:
        The saved `ApiToken` and the full token text. This is the only moment when the full
        text exists. The caller must show it once and never save it.

    Raises:
        TokenLimitError: If the user already has `API_TOKEN_MAX_PER_USER` active tokens.
        ValueError: If the name is empty.
    """
    now = now or timezone.now()
    name = name.strip()[:MAX_NAME_CHARS]
    if not name:
        msg = "Enter a name for the token."
        raise ValueError(msg)
    if len(active_tokens(user, now)) >= conf.API_TOKEN_MAX_PER_USER:
        raise TokenLimitError
    days = conf.API_TOKEN_EXPIRY_DAYS
    expires_at = now + timedelta(days=days) if days else None
    for _ in range(MAX_PREFIX_TRIES):
        prefix = secrets.token_hex(4)
        raw = f"{TOKEN_PREFIX}_{prefix}_{secrets.token_hex(24)}"
        try:
            with transaction.atomic():
                token = ApiToken.objects.create(
                    user=user,
                    name=name,
                    prefix=prefix,
                    token_hash=digest(raw),
                    password_stamp=password_stamp(user),
                    expires_at=expires_at,
                )
        except IntegrityError:
            continue  # The prefix exists already. Try another one.
        return token, raw
    msg = "Could not make a unique token prefix."
    raise RuntimeError(msg)


def authenticate(raw: str, now: datetime | None = None) -> ApiToken:
    """Find the token for a full token text and check that it can be used.

    The checks run in a fixed order. Every failure for an unknown or wrong token gives the same
    `invalid_token` answer, so a client cannot learn which part was wrong.

    Args:
        raw: The token text from the `Authorization: Bearer` header.
        now: The current time. Tests set it.

    Returns:
        The `ApiToken`, with its `user` loaded.

    Raises:
        TokenError: With code `invalid_token` for an unknown, wrong, revoked or stale token, or
            for an inactive user. With code `token_expired` when the token reached its end date.
    """
    now = now or timezone.now()
    match = TOKEN_RE.match(raw.strip())
    if match is None:
        raise TokenError("invalid_token", "The token is not valid.")
    token = ApiToken.objects.select_related("user").filter(prefix=match.group(1)).first()
    if token is None or not hmac.compare_digest(token.token_hash, digest(raw.strip())):
        raise TokenError("invalid_token", "The token is not valid.")
    if token.revoked_at is not None:
        raise TokenError("invalid_token", "The token is not valid.")
    if token.is_expired(now):
        raise TokenError("token_expired", "The token has expired. Make a new one.")
    user = token.user
    if not user.is_active or token.password_stamp != password_stamp(user):
        raise TokenError("invalid_token", "The token is not valid.")
    return token


def touch(token: ApiToken, now: datetime | None = None) -> None:
    """Save the time of use. It writes at most once a minute for each token.

    The limit keeps the number of database writes low when a client calls the API often.

    Args:
        token: The token that was used. The function also sets `last_used_at` on this object.
        now: The time of use. The default is the current time.
    """
    now = now or timezone.now()
    if token.last_used_at is None or now - token.last_used_at >= LAST_USED_STEP:
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=now)
        token.last_used_at = now


def revoke(token: ApiToken, now: datetime | None = None) -> bool:
    """Revoke one token. Return False if it was already revoked.

    Args:
        token: The token to revoke.
        now: The time of revocation. The default is the current time.

    Returns:
        True if this call revoked the token. False if it was revoked before.
    """
    if token.revoked_at is not None:
        return False
    token.revoked_at = now or timezone.now()
    token.save(update_fields=["revoked_at"])
    return True


def revoke_all(user: AbstractBaseUser, now: datetime | None = None) -> int:
    """Revoke every token of a user that is not revoked. Return how many were revoked.

    A token that is expired but not revoked is also marked as revoked.

    Args:
        user: The owner of the tokens.
        now: The time of revocation. The default is the current time.

    Returns:
        The number of rows that the call changed.
    """
    return ApiToken.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=now or timezone.now()
    )
