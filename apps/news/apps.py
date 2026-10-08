"""App configuration for the news app."""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    """Configuration for the news app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.news"
