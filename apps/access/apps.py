"""App configuration for the access rules."""

from django.apps import AppConfig


class AccessConfig(AppConfig):
    """Feature permissions and subscriptions of the users."""

    name = "apps.access"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Connect the signal that starts the trial of a new user."""
        from . import signals  # noqa: F401, PLC0415
