import pytest
from django.test import Client


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """The real hasher is slow on purpose. The tests do not need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


PASSWORD = "pw-access-test-1"


@pytest.fixture
def member(django_user_model):
    return django_user_model.objects.create_user("member", "member@example.com", PASSWORD)


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
