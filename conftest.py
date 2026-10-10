import pytest

from apps.siteconfig import conf


@pytest.fixture(autouse=True)
def fresh_site_settings():
    """The saved settings are cached in memory. Each test starts without the cache."""
    conf.invalidate()
    yield
    conf.invalidate()


@pytest.fixture
def expire():
    """Return a function that makes the subscription of a user end an hour ago."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from apps.access.models import Subscription  # noqa: PLC0415

    def _expire(user) -> None:
        Subscription.objects.filter(user=user).update(ends_at=timezone.now() - timedelta(hours=1))

    return _expire
