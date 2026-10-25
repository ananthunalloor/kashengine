"""Save and reset the settings (used by the dashboard)."""

import json
from typing import Any

from django.db import transaction

from . import conf, crypto
from .models import Setting
from .registry import SPECS, validate


def save(values: dict[str, Any], user=None) -> list[str]:
    """Save values. Return the keys that changed. A secret with an empty value is not changed.

    The function checks each value with `validate`. It saves a non-secret value only if it is
    different from the current value. It encrypts a secret before it saves it. All writes are
    in one transaction. At the end it clears the cache of this process.

    Args:
        values: A dict from the setting key to the raw value. Each key must be a known setting.
        user: The admin who saves the values, or None.

    Returns:
        The keys that the function saved.

    Raises:
        KeyError: If a key is not a known setting.
        ValueError: If a value is not valid. Then nothing is saved.
    """
    changed = []
    with transaction.atomic():
        for key, raw in values.items():
            spec = SPECS[key]
            value = validate(spec, raw)
            if spec.secret:
                if not value:
                    continue
                stored = crypto.encrypt(value)
            else:
                stored = json.dumps(value)
            if not spec.secret and conf.get(key) == value:
                continue  # Nothing changed. We save a row only for a new value.
            Setting.objects.update_or_create(
                key=key, defaults={"value": stored, "updated_by": user}
            )
            changed.append(key)
    conf.invalidate()
    return changed


def reset(keys: list[str]) -> int:
    """Delete the saved values. The environment values are used again. Return how many.

    Args:
        keys: The setting keys to reset. A key that has no saved value is ignored.

    Returns:
        The number of deleted rows.
    """
    count = Setting.objects.filter(key__in=keys).delete()[0]
    conf.invalidate()
    return count
