import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps.delivery.models import DeliveryPreference
from apps.ops import health, jobs, metrics

PASSWORD = "pw-ops-test-1"


@pytest.fixture(autouse=True)
def legacy_domain_unit_context(settings, request):
    """Exercise original domain actions in isolation; test_archive covers host authorization."""
    if request.node.path.name == "test_react_workspace.py":
        return
    settings.ROOT_URLCONF = "apps.web.tests.legacy_urls"
    settings.MIDDLEWARE = [
        "apps.web.tests.legacy_urls.LegacyRendererContext"
        if item == "apps.web.archive.ArchiveMiddleware"
        else item
        for item in settings.MIDDLEWARE
    ]


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    """The real hasher is slow on purpose. The tests do not need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def clean_cache():
    """The health result is cached. Each test starts without it."""
    cache.clear()
    yield
    cache.clear()


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


def _logged_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def member_client(member):
    return _logged_in(member)


@pytest.fixture
def staff_client(staff):
    return _logged_in(staff)


@pytest.fixture
def boss_client(boss):
    return _logged_in(boss)


@pytest.fixture
def queue(monkeypatch):
    """Replace the queue. The list gets (task name, args, task id) for each job that is sent."""
    sent: list[tuple[str, list, str]] = []
    monkeypatch.setattr(
        jobs, "dispatch", lambda name, args, task_id: sent.append((name, args, task_id))
    )
    return sent


@pytest.fixture
def offline(monkeypatch):
    """No Redis, no worker, no LLM server: the page tests do not wait for the network."""
    ok = health.Check("fake", "Fake", health.OK, "fine")
    monkeypatch.setattr(health, "run_all", lambda **_kw: [("Services", [ok])])
    monkeypatch.setattr(metrics, "redis_stats", lambda: None)
    monkeypatch.setattr(metrics, "worker_stats", lambda: None)
