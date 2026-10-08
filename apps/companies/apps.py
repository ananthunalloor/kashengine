"""App configuration for the companies app."""

from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    """Configuration of the companies app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.companies"
