"""App configuration for the ops app.

Django loads `OpsConfig` because `apps.ops` is in `INSTALLED_APPS`. The `ready` method imports
the signal module, which connects the receivers that record task runs and logins.
"""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """The app config of the Ops pages: health, jobs, logs, metrics, and user monitoring.

    The app label is `ops`. The models use `BigAutoField` for their primary keys.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Operations"

    def ready(self) -> None:
        """Connect the Celery and login signals.

        The import of `apps.ops.signals` runs the `connect` decorators in that module. Django calls
        this method once at start-up, in each process (web server, worker, and beat).
        """
        from . import signals  # noqa: F401, PLC0415  # Import registers the receivers.
