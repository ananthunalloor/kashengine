"""App config for django-celery-beat.

The tables of django-celery-beat use AutoField. Our default is BigAutoField. Without this
class, Django wants a new migration for a library that we do not own.
"""

from django_celery_beat.apps import BeatConfig as LibraryBeatConfig


class BeatConfig(LibraryBeatConfig):
    """Keep the id type of the library migrations."""

    default_auto_field = "django.db.models.AutoField"
