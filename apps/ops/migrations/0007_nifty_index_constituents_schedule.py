"""Schedule the daily official Nifty constituent refresh."""

from django.conf import settings
from django.db import migrations


def seed(apps, schema_editor):
    """Add the refresh without modifying an operator-edited schedule."""
    crontabs = apps.get_model("django_celery_beat", "CrontabSchedule")
    tasks = apps.get_model("django_celery_beat", "PeriodicTask")
    cron, _created = crontabs.objects.get_or_create(
        minute="30",
        hour="6",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=settings.TIME_ZONE,
    )
    tasks.objects.get_or_create(
        name="refresh-nifty-index-constituents",
        defaults={
            "task": "markets.refresh_index_constituents",
            "crontab": cron,
            "enabled": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0006_exchange_instrument_schedule"),
        ("django_celery_beat", "0014_remove_clockedschedule_enabled"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
