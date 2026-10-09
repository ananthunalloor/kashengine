"""The config page must never show a secret."""

import pytest

from apps.ops import configview


@pytest.mark.parametrize(
    "name",
    ["TELEGRAM_BOT_TOKEN", "DJANGO_SECRET_KEY", "DB_PASSWORD", "SOME_API_KEY", "PRIVATE_KEY"],
)
def test_a_secret_is_hidden(name):
    assert configview.display_value(name, "super-secret-value") == "set (hidden)"
    assert configview.display_value(name, "") == "not set"


def test_a_url_with_a_password_is_masked():
    shown = configview.display_value("CELERY_BROKER_URL", "redis://user:pw123@cache:6379/0")

    assert "pw123" not in shown
    assert "user" not in shown
    assert shown == "redis://<hidden>@cache:6379/0"


def test_a_url_without_a_login_is_shown():
    assert configview.display_value("LLM_BASE_URL", "http://ollama:11434") == "http://ollama:11434"


def test_chat_ids_are_counted_not_shown():
    assert configview.display_value("TELEGRAM_CHAT_IDS", ["111", "222"]) == "2 chat(s)"


def test_lists_and_empty_values():
    assert configview.display_value("ALLOWED_HOSTS", ["a", "b"]) == "a, b"
    assert configview.display_value("ALLOWED_HOSTS", []) == "not set"
    assert configview.display_value("DEBUG", False) == "False"


def test_the_page_data_has_no_secret(settings):
    settings.TELEGRAM_BOT_TOKEN = "123456:SECRET-TOKEN-VALUE"
    settings.SECRET_KEY = "very-secret-django-key"
    settings.CELERY_BROKER_URL = "redis://:brokerpw@redis:6379/0"

    text = repr(configview.sections())

    for secret in ("SECRET-TOKEN-VALUE", "very-secret-django-key", "brokerpw"):
        assert secret not in text
    assert "TELEGRAM_BOT_TOKEN" in text


def test_the_database_summary_has_no_password(settings, monkeypatch):
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "db",
        "NAME": "kash",
        "PASSWORD": "dbpw-secret",
        "USER": "kash",
    }
    monkeypatch.setitem(settings.DATABASES, "default", config)

    summary = configview.database_summary()

    assert summary == "postgresql, db, kash"
