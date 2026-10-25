"""Read the settings, with the values that an admin saved on the dashboard.

    from apps.siteconfig import conf

    conf.LLM_MODEL            # the value from the dashboard, else from the environment
    conf.get("LLM_MODEL")     # the same

The saved values are kept in memory for a few seconds in each process (web, worker, beat). A
change on the dashboard is live in the same process at once and in the other processes after
CACHE_SECONDS. If the database cannot answer, the code uses the environment values.
"""

import json
import logging
import time
from typing import Any

from django.conf import settings
from django.db import transaction

from . import crypto
from .models import Setting
from .registry import SPECS, validate

logger = logging.getLogger(__name__)

CACHE_SECONDS = 5.0

_cache: dict[str, Any] | None = None
_loaded_at = 0.0


def _decode(row: Setting) -> Any:
    """Turn the saved text of one setting into a value.

    Args:
        row: The saved setting.

    Returns:
        The clean value. A secret is decrypted. None if the setting no longer exists, if a
        secret cannot be decrypted, or if the saved value is not valid for its spec. A
        secret that is saved as an empty text gives an empty text.
    """
    spec = SPECS.get(row.key)
    if spec is None:
        return None  # A setting that no longer exists.
    text = row.value
    if spec.secret:
        return crypto.decrypt(text) if text else ""
    try:
        return validate(spec, json.loads(text))
    except ValueError:
        logger.warning("The saved value of %s is not valid. The default is used.", row.key)
        return None


def _load() -> dict[str, Any]:
    """Read all saved values. An unreadable value is left out.

    Returns:
        A dict from the setting key to the clean value.
    """
    values: dict[str, Any] = {}
    with transaction.atomic():  # A savepoint, so an error does not break a caller's transaction.
        rows = list(Setting.objects.all())
    for row in rows:
        decoded = _decode(row)
        if decoded is not None:
            values[row.key] = decoded
    return values


def overrides() -> dict[str, Any]:
    """Return the values that were saved on the dashboard. A secret is included (decrypted).

    The result is kept in memory for `CACHE_SECONDS` seconds in each process. If the database
    cannot answer (for example before `migrate`), the result is empty, so the caller uses the
    environment values.

    Returns:
        A dict from the setting key to the clean value. Do not change it.
    """
    global _cache, _loaded_at  # noqa: PLW0603
    now = time.monotonic()
    if _cache is None or now - _loaded_at > CACHE_SECONDS:
        try:
            _cache = _load()
        except Exception as exc:
            # The table is missing (before migrate), or the database is down: use the defaults.
            logger.debug("Saved settings cannot be read: %s", exc)
            _cache = {}
        _loaded_at = now
    return _cache


def invalidate() -> None:
    """Forget the saved values in this process. The next read asks the database."""
    global _cache  # noqa: PLW0603
    _cache = None


def get(key: str) -> Any:
    """Return the value of a setting: the dashboard value, else the environment value.

    Args:
        key: The name of a setting that the registry knows, for example `LLM_MODEL`.

    Returns:
        The value.

    Raises:
        AttributeError: If the key is not a setting that the dashboard manages.
    """
    if key not in SPECS:
        msg = f"{key} is not a setting that the dashboard manages."
        raise AttributeError(msg)
    saved = overrides()
    if key in saved:
        return saved[key]
    return getattr(settings, key)


def default(key: str) -> Any:
    """Return the value from the environment or the default. A dashboard value is ignored.

    Args:
        key: The name of a Django setting.

    Returns:
        The value of that Django setting.
    """
    return getattr(settings, key)


def is_saved(key: str) -> bool:
    """Return True if an admin saved a value for this setting.

    Args:
        key: The name of a setting.

    Returns:
        True if the dashboard has a valid saved value for the key.
    """
    return key in overrides()


def __getattr__(name: str) -> Any:
    """Allow `conf.LLM_MODEL`."""
    if name.isupper():
        return get(name)
    raise AttributeError(name)
