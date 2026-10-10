"""Saved settings: encryption, the cache, and the rules for saving."""

import json

import pytest
from django.db import connection

from apps.siteconfig import conf, crypto, service
from apps.siteconfig.models import Setting

pytestmark = pytest.mark.django_db


def test_a_secret_is_encrypted_in_the_database(settings):
    service.save({"TELEGRAM_BOT_TOKEN": "123456:SECRET-TOKEN-VALUE"})

    stored = Setting.objects.get(key="TELEGRAM_BOT_TOKEN").value
    assert "SECRET-TOKEN-VALUE" not in stored
    assert crypto.decrypt(stored) == "123456:SECRET-TOKEN-VALUE"
    with connection.cursor() as cursor:  # Look at the raw row, too.
        cursor.execute("SELECT value FROM siteconfig_setting")
        assert "SECRET-TOKEN-VALUE" not in cursor.fetchone()[0]
    assert conf.TELEGRAM_BOT_TOKEN == "123456:SECRET-TOKEN-VALUE"


def test_an_empty_secret_does_not_change_the_saved_one():
    service.save({"TELEGRAM_BOT_TOKEN": "111:aaa"})

    changed = service.save({"TELEGRAM_BOT_TOKEN": ""})

    assert changed == []
    assert conf.TELEGRAM_BOT_TOKEN == "111:aaa"


def test_a_secret_cannot_be_read_after_the_key_changes(settings):
    service.save({"TELEGRAM_BOT_TOKEN": "111:aaa"})

    settings.SECRET_KEY = "another-key-for-this-test-only-0123456789"
    conf.invalidate()

    assert conf.TELEGRAM_BOT_TOKEN == ""  # Not set. The admin must enter it again.


def test_a_separate_encryption_key_survives_a_secret_key_change(settings):
    settings.SETTINGS_ENCRYPTION_KEY = "the-encryption-key"
    service.save({"TELEGRAM_BOT_TOKEN": "111:aaa"})

    settings.SECRET_KEY = "another-key-for-this-test-only-0123456789"
    conf.invalidate()

    assert conf.TELEGRAM_BOT_TOKEN == "111:aaa"


def test_a_saved_value_wins_over_the_environment(settings):
    settings.LLM_MODEL = "from-env"
    assert conf.LLM_MODEL == "from-env"

    service.save({"LLM_MODEL": "from-dashboard"})

    assert conf.LLM_MODEL == "from-dashboard"
    assert conf.is_saved("LLM_MODEL")
    assert conf.default("LLM_MODEL") == "from-env"


def test_reset_goes_back_to_the_environment(settings):
    settings.LLM_MODEL = "from-env"
    service.save({"LLM_MODEL": "from-dashboard"})

    assert service.reset(["LLM_MODEL"]) == 1

    assert conf.LLM_MODEL == "from-env"
    assert not conf.is_saved("LLM_MODEL")


def test_a_value_that_equals_the_current_one_saves_no_row(settings):
    settings.LLM_TIMEOUT_SECONDS = 180

    changed = service.save({"LLM_TIMEOUT_SECONDS": "180", "LLM_MODEL": settings.LLM_MODEL})

    assert changed == []
    assert not Setting.objects.exists()


def test_a_bad_value_is_refused_and_nothing_is_saved():
    with pytest.raises(ValueError, match=r"."):
        service.save({"LLM_TIMEOUT_SECONDS": "-5"})

    assert not Setting.objects.exists()


def test_the_user_who_saved_is_kept(django_user_model):
    user = django_user_model.objects.create_user("who", password="pw-test-12345")

    service.save({"LLM_MODEL": "x"}, user)

    assert Setting.objects.get(key="LLM_MODEL").updated_by == user


def test_a_broken_row_is_ignored_and_the_default_is_used(settings):
    settings.LLM_TIMEOUT_SECONDS = 180
    Setting.objects.create(key="LLM_TIMEOUT_SECONDS", value=json.dumps("not a number"))
    Setting.objects.create(key="NO_SUCH_SETTING", value='"x"')
    conf.invalidate()

    assert conf.LLM_TIMEOUT_SECONDS == 180


def test_the_saved_values_are_cached_in_memory(django_assert_num_queries):
    service.save({"LLM_MODEL": "x"})
    conf.invalidate()
    assert conf.LLM_MODEL == "x"  # One query: it loads all the saved values.

    with django_assert_num_queries(0):
        assert conf.LLM_MODEL == "x"
        assert conf.LLM_BASE_URL


def test_the_cache_ends_after_a_few_seconds(monkeypatch):
    service.save({"LLM_MODEL": "x"})
    assert conf.LLM_MODEL == "x"
    Setting.objects.filter(key="LLM_MODEL").update(value=json.dumps("changed elsewhere"))

    assert conf.LLM_MODEL == "x"  # Still the cached value.
    monkeypatch.setattr(conf, "_loaded_at", conf._loaded_at - conf.CACHE_SECONDS - 1)
    assert conf.LLM_MODEL == "changed elsewhere"  # Another process (the worker) sees it.


def test_an_unknown_setting_is_an_error():
    with pytest.raises(AttributeError):
        conf.get("NOT_A_SETTING")
    with pytest.raises(AttributeError):
        conf.NOT_A_SETTING  # noqa: B018


@pytest.mark.django_db(transaction=False)
def test_the_defaults_are_used_when_the_table_cannot_be_read(monkeypatch, settings):
    settings.LLM_MODEL = "from-env"

    def broken():
        msg = "the table does not exist"
        raise RuntimeError(msg)

    monkeypatch.setattr(conf, "_load", broken)
    conf.invalidate()

    assert conf.LLM_MODEL == "from-env"
