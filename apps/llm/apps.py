"""App configuration for the llm app."""

from django.apps import AppConfig


class LlmConfig(AppConfig):
    """Django configuration for the llm app.

    The app holds the client for the local LLM server (Ollama) and the `llm_check` command. It
    has no models. Django loads this class because `apps.llm` is in `INSTALLED_APPS`.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.llm"
