import pytest
from django.test import Client
from django.utils import timezone

from apps.delivery.models import DeliveryPreference


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """The real hasher is slow on purpose. The tests do not need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


PASSWORD = "pw-access-test-1"


@pytest.fixture(autouse=True)
def legacy_feature_unit_context(settings, request):
    """Test original feature rendering separately from the archive's superuser boundary."""
    if request.node.path.name != "test_web.py":
        return
    settings.ROOT_URLCONF = "apps.web.tests.legacy_urls"
    settings.MIDDLEWARE = [
        "apps.web.tests.legacy_urls.LegacyRendererContext"
        if item == "apps.web.archive.ArchiveMiddleware"
        else item
        for item in settings.MIDDLEWARE
    ]


@pytest.fixture
def member(django_user_model):
    user = django_user_model.objects.create_user("member", "member@example.com", PASSWORD)
    DeliveryPreference.objects.create(user=user, email_verified_at=timezone.now())
    return user


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(
        "staff", "staff@example.com", PASSWORD, is_staff=True
    )


@pytest.fixture
def boss(django_user_model):
    return django_user_model.objects.create_superuser("boss", "boss@example.com", PASSWORD)


def client_for(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def member_client(member):
    return client_for(member)


@pytest.fixture
def staff_client(staff):
    return client_for(staff)


@pytest.fixture
def boss_client(boss):
    return client_for(boss)
