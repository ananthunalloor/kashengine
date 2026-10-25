"""Start the trial when a new user is made."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import service


@receiver(post_save, sender=get_user_model(), dispatch_uid="access_start_trial")
def start_trial_for_new_user(sender, instance, created, raw=False, **kwargs) -> None:
    """Start the trial for a new user. A fixture load (`raw`) does not start it.

    Args:
        sender: The user model. Django sets it.
        instance: The user that was saved.
        created: True if the save made a new row.
        raw: True when Django loads a fixture. Then the function does nothing.
        kwargs: Other values that the signal sends. The function does not use them.
    """
    if created and not raw:
        service.start_trial(instance)
