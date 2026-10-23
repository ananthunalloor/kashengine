"""Add opt-in provider schedules without modifying existing operator-edited entries."""

from django.conf import settings
from django.db import migrations


def seed(apps, schema_editor):
    """The tasks themselves skip all provider calls until Upstox is enabled."""
    crontabs = apps.get_model("django_celery_beat", "CrontabSchedule")
    tasks = apps.get_model("django_celery_beat", "PeriodicTask")
    for name, task, minute, hour in (
        ("upstox-company-quotes", "markets.upstox_quotes", "*/5", "*"),
        ("upstox-data-refresh", "markets.upstox_refresh", "10", "*/6"),
    ):
        cron, _ = crontabs.objects.get_or_create(
            minute=minute, hour=hour, day_of_week="*", day_of_month="*",
            month_of_year="*", timezone=settings.TIME_ZONE,
        )
        tasks.objects.get_or_create(
            name=name, defaults={"task": task, "crontab": cron, "enabled": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0004_alter_backupconfiguration_endpoint_url"),
        ("django_celery_beat", "0014_remove_clockedschedule_enabled"),
    ]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
