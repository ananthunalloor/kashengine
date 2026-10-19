import pytest


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """The real hasher is slow on purpose. The tests do not need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def legacy_renderer_unit_context(settings, request):
    """Keep archived renderer tests independent of the deployed host authorization gate."""
    if request.node.path.name not in {
        "test_views.py",
        "test_landing.py",
        "test_account_tokens.py",
        "test_proxy.py",
    }:
        return
    if "react_shell" in request.node.name or "reports_preview" in request.node.name:
        return
    settings.ROOT_URLCONF = "apps.web.tests.legacy_urls"
    settings.MIDDLEWARE = [
        "apps.web.tests.legacy_urls.LegacyRendererContext"
        if item == "apps.web.archive.ArchiveMiddleware"
        else item
        for item in settings.MIDDLEWARE
    ]
