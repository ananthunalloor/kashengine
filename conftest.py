import pytest

from apps.siteconfig import conf


@pytest.fixture(autouse=True)
def fresh_site_settings():
    """The saved settings are cached in memory. Each test starts without the cache."""
    conf.invalidate()
    yield
    conf.invalidate()
