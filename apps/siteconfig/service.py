"""Save and reset the settings (used by the dashboard)."""

import json
from typing import Any

from django.db import transaction

from . import conf, crypto
from .models import Setting
from .registry import SPECS, validate


def save(values: dict[str, Any], user=None) -> list[str]:
    """Save values. Return the keys that changed. A secret with an empty value is not changed."""
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
    """Delete the saved values. The environment values are used again. Return how many."""
    count = Setting.objects.filter(key__in=keys).delete()[0]
    conf.invalidate()
    return count
