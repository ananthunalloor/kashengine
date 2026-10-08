"""App config for the web pages."""

from django.apps import AppConfig


class WebConfig(AppConfig):
    """Config for the web app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.web"
