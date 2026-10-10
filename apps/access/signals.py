"""Start the trial when a new user is made."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import service


@receiver(post_save, sender=get_user_model(), dispatch_uid="access_start_trial")
def start_trial_for_new_user(sender, instance, created, raw=False, **kwargs) -> None:
    """A new user gets the trial. A fixture load (`raw`) does not."""
    if created and not raw:
        service.start_trial(instance)
