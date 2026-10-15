"""App configuration for the markets app.

Django loads `MarketsConfig` from `INSTALLED_APPS`. The app holds the quotes, the instruments, the
prediction and its evaluation.
"""

from django.apps import AppConfig


class MarketsConfig(AppConfig):
    """Configuration of the markets app (`apps.markets`).

    The app uses `BigAutoField` for the primary keys of its models.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.markets"
