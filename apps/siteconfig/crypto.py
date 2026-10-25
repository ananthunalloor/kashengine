"""Encrypt secrets (the Telegram bot token, for example) before they go in the database.

The key comes from SETTINGS_ENCRYPTION_KEY, or from SECRET_KEY if that is empty. If you change
the key, the saved secrets cannot be read any more. They then count as "not set", and an admin
must enter them again.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

KEY_CONTEXT = b"kash-engine-site-settings:"


def _fernet() -> Fernet:
    """Return the Fernet object for the current key.

    The key comes from `SETTINGS_ENCRYPTION_KEY`, or from `SECRET_KEY` if that is empty. A
    SHA-256 hash of the key and a fixed context text gives the 32 bytes that Fernet needs.

    Returns:
        A Fernet object.
    """
    material = (getattr(settings, "SETTINGS_ENCRYPTION_KEY", "") or settings.SECRET_KEY).encode()
    digest = hashlib.sha256(KEY_CONTEXT + material).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(text: str) -> str:
    """Return the encrypted text.

    Args:
        text: The plain text, for example a Telegram bot token.

    Returns:
        The Fernet token as text. The database keeps this value.
    """
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str | None:
    """Return the plain text, or None if the token cannot be read with the current key.

    Args:
        token: The Fernet token that `encrypt` made.

    Returns:
        The plain text. None if the key changed or the token is not valid. The function writes
        a warning to the log in this case, without the token.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning("A saved secret cannot be decrypted. Was the key changed?")
        return None
