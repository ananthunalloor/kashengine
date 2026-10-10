"""App configuration for the site settings store."""

from django.apps import AppConfig


class SiteConfigConfig(AppConfig):
    """Settings that an admin can change on the dashboard (stored in the database)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.siteconfig"
    verbose_name = "Site settings"
