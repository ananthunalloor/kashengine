"""Schedule dynamic forecasts, chronological training and independent audits."""

from django.conf import settings
from django.db import migrations


def seed(apps, schema_editor):
    """Preserve any operator-edited task with the same name."""
    crontabs = apps.get_model("django_celery_beat", "CrontabSchedule")
    tasks = apps.get_model("django_celery_beat", "PeriodicTask")
    for name, task, minute, hour in (
        ("refresh-dynamic-forecasts", "markets.refresh_forecasts", "*/15", "*"),
        ("prediction-watchdog", "markets.watchdog", "7-59/15", "*"),
        ("train-forecast-models", "markets.train_forecasts", "0", "5"),
    ):
        cron, _created = crontabs.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone=settings.TIME_ZONE,
        )
        tasks.objects.get_or_create(
            name=name, defaults={"task": task, "crontab": cron, "enabled": True}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0007_nifty_index_constituents_schedule"),
        ("markets", "0007_forecast_evidence"),
        ("django_celery_beat", "0014_remove_clockedschedule_enabled"),
    ]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
