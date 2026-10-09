"""App configuration for the ops app."""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """Admin tools: health, jobs, logs, metrics, and user monitoring."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Operations"

    def ready(self) -> None:
        """Connect the Celery and login signals."""
        from . import signals  # noqa: F401, PLC0415  # Import registers the receivers.
