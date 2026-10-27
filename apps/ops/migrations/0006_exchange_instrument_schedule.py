"""Schedule the daily NSE/BSE instrument catalog refresh."""

from django.conf import settings
from django.db import migrations


def seed(apps, schema_editor):
    """Add the daily refresh without changing an operator-edited schedule."""
    crontabs = apps.get_model("django_celery_beat", "CrontabSchedule")
    tasks = apps.get_model("django_celery_beat", "PeriodicTask")
    cron, _created = crontabs.objects.get_or_create(
        minute="20",
        hour="6",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=settings.TIME_ZONE,
    )
    tasks.objects.get_or_create(
        name="refresh-exchange-instruments",
        defaults={"task": "markets.refresh_instruments", "crontab": cron, "enabled": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0005_upstox_schedule"),
        ("django_celery_beat", "0014_remove_clockedschedule_enabled"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
