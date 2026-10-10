"""Save the first schedule in the database (django-celery-beat tables)."""

from django.conf import settings
from django.db import migrations

from apps.ops.defaults import DEFAULT_SCHEDULE


def seed_schedule(apps, schema_editor):
    """Add the default entries. An entry with the same name is not changed."""
    Crontab = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    for name, task, minute, hour, day_of_week in DEFAULT_SCHEDULE:
        crontab, _created = Crontab.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month="*",
            month_of_year="*",
            timezone=settings.TIME_ZONE,
        )
        PeriodicTask.objects.get_or_create(
            name=name, defaults={"task": task, "crontab": crontab, "enabled": True}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0001_initial"),
        ("django_celery_beat", "0014_remove_clockedschedule_enabled"),
    ]

    operations = [migrations.RunPython(seed_schedule, migrations.RunPython.noop)]
