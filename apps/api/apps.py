"""App configuration for the REST API."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """The read-only REST API at `/api/v1/` and its API tokens."""

    name = "apps.api"
    default_auto_field = "django.db.models.BigAutoField"
