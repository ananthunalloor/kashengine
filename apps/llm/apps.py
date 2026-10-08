"""App configuration for the llm app."""

from django.apps import AppConfig


class LlmConfig(AppConfig):
    """Configuration for the llm app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.llm"
