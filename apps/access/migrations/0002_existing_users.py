"""Give a subscription to the users that exist before this app.

They get a gift that does not end, so nobody is locked out when an admin turns on
"Require a subscription". An admin can end or change each one on Ops > Users.
"""

from django.conf import settings
from django.db import migrations

NOTE = "User from before subscriptions"


def grandfather(apps, schema_editor):
    """Add a gift subscription for each user without one."""
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    Subscription = apps.get_model("access", "Subscription")
    Event = apps.get_model("access", "SubscriptionEvent")
    have = set(Subscription.objects.values_list("user_id", flat=True))
    for user in User.objects.exclude(pk__in=have):
        Subscription.objects.create(user=user, kind="gift", ends_at=None)
        Event.objects.create(user=user, action="given", kind="gift", ends_at=None, note=NOTE)


class Migration(migrations.Migration):
    dependencies = [("access", "0001_store")]

    operations = [migrations.RunPython(grandfather, migrations.RunPython.noop)]
