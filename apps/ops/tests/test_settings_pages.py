"""The Ops pages for settings: access, saving, secrets, and the audit trail."""

import pytest
from django.urls import reverse

from apps.ops.models import AuditEvent
from apps.siteconfig import conf, registry
from apps.siteconfig.models import Setting

pytestmark = pytest.mark.django_db

GROUP_KEYS = [key for key, _title, _help in registry.GROUPS]
SECRET_TOKEN = "123456:VERY-SECRET-TOKEN-VALUE"


def _url(group: str) -> str:
    return reverse("ops:settings_group", args=[group])


def _post(client, group: str, **values):
    return client.post(_url(group), values)


# Access


def test_the_settings_pages_need_a_login(client):
    for url in [reverse("ops:settings"), *map(_url, GROUP_KEYS)]:
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url


def test_a_normal_user_gets_a_403_on_the_settings_pages(member_client):
    for url in [reverse("ops:settings"), *map(_url, GROUP_KEYS)]:
        assert member_client.get(url).status_code == 403


@pytest.mark.parametrize("client_name", ["staff_client", "boss_client"])
def test_staff_and_superuser_can_open_every_group(request, client_name, offline):
    client = request.getfixturevalue(client_name)

    assert client.get(reverse("ops:settings")).status_code == 200
    for group in GROUP_KEYS:
        assert client.get(_url(group)).status_code == 200


def test_an_unknown_group_is_a_404(boss_client):
    assert boss_client.get(_url("nonsense")).status_code == 404


def test_a_staff_user_cannot_save(staff_client):
    response = _post(staff_client, "llm", LLM_MODEL="sneaky")

    assert response.status_code == 403
    assert not Setting.objects.filter(key="LLM_MODEL").exists()


def test_a_save_needs_the_csrf_token(boss):
    from django.test import Client  # noqa: PLC0415

    client = Client(enforce_csrf_checks=True)
    client.force_login(boss)

    assert client.post(_url("llm"), {"LLM_MODEL": "x"}).status_code == 403


def test_the_index_lists_every_group(boss_client, offline):
    page = boss_client.get(reverse("ops:settings")).content.decode()

    for group in GROUP_KEYS:
        assert f'href="{_url(group)}"' in page


def test_the_menu_has_the_new_ops_links(boss_client, offline):
    page = boss_client.get(reverse("ops:overview")).content.decode()

    for name in ("ops:settings", "ops:schedule", "ops:feeds", "ops:instruments"):
        assert f'href="{reverse(name)}"' in page


# Saving


def _llm_values(**overrides):
    values = {spec.key: "" for spec in registry.specs_in("llm")}
    values.update({s.key: conf.get(s.key) for s in registry.specs_in("llm") if not s.secret})
    values.update(overrides)
    return {key: ("on" if value is True else value) for key, value in values.items()}


def test_a_superuser_saves_a_value(boss_client, boss):
    response = boss_client.post(_url("llm"), _llm_values(LLM_MODEL="my-model"))

    assert response.status_code == 302
    assert conf.LLM_MODEL == "my-model"
    assert Setting.objects.get(key="LLM_MODEL").updated_by == boss


def test_the_change_goes_in_the_audit_trail(boss_client, settings):
    settings.LLM_MODEL = "old-model"
    conf.invalidate()

    boss_client.post(_url("llm"), _llm_values(LLM_MODEL="new-model"))

    event = AuditEvent.objects.get(action="change settings")
    assert "LLM_MODEL: old-model -> new-model" in event.detail
    assert event.actor_name == "boss"


def test_a_bad_value_saves_nothing_and_shows_the_error(boss_client):
    response = boss_client.post(_url("llm"), _llm_values(LLM_TIMEOUT_SECONDS="abc"))

    assert response.status_code == 200
    assert not Setting.objects.exists()
    assert not AuditEvent.objects.filter(action="change settings").exists()
    assert "Nothing was saved" in response.content.decode()


def test_a_value_out_of_range_is_refused(boss_client):
    response = boss_client.post(_url("llm"), _llm_values(LLM_TIMEOUT_SECONDS="99999999"))

    assert response.status_code == 200
    assert not Setting.objects.filter(key="LLM_TIMEOUT_SECONDS").exists()


def test_the_use_default_box_deletes_the_saved_value(boss_client):
    boss_client.post(_url("llm"), _llm_values(LLM_MODEL="my-model"))
    assert conf.is_saved("LLM_MODEL")

    boss_client.post(_url("llm"), _llm_values(reset__LLM_MODEL="on"))

    assert not conf.is_saved("LLM_MODEL")
    event = AuditEvent.objects.filter(action="change settings").latest("pk")
    assert "LLM_MODEL: back to the default" in event.detail


def test_a_save_without_a_change_writes_no_audit_event(boss_client):
    response = boss_client.post(_url("llm"), _llm_values())

    assert response.status_code == 302
    assert not AuditEvent.objects.filter(action="change settings").exists()


def test_a_url_setting_must_be_a_web_address(boss_client):
    values = {s.key: conf.get(s.key) for s in registry.specs_in("llm") if not s.secret}
    values["LLM_BASE_URL"] = "ftp://example.com"

    response = boss_client.post(_url("llm"), values)

    assert response.status_code == 200
    assert not Setting.objects.filter(key="LLM_BASE_URL").exists()


# Secrets


def _telegram_values(**overrides):
    values = {
        "TELEGRAM_CHAT_IDS": "",
        "TELEGRAM_API_URL": conf.get("TELEGRAM_API_URL"),
        "TELEGRAM_TIMEOUT_SECONDS": conf.get("TELEGRAM_TIMEOUT_SECONDS"),
    }
    values.update(overrides)
    return values


def test_the_telegram_token_is_saved_encrypted_and_never_shown(boss_client):
    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=SECRET_TOKEN))

    assert conf.TELEGRAM_BOT_TOKEN == SECRET_TOKEN
    assert SECRET_TOKEN not in Setting.objects.get(key="TELEGRAM_BOT_TOKEN").value
    for client_page in (boss_client.get(_url("telegram")), boss_client.get(reverse("ops:config"))):
        assert SECRET_TOKEN not in client_page.content.decode()
    assert SECRET_TOKEN not in boss_client.get(reverse("ops:settings")).content.decode()


def test_the_token_is_not_in_the_audit_trail(boss_client):
    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=SECRET_TOKEN))

    event = AuditEvent.objects.get(action="change settings")

    assert "TELEGRAM_BOT_TOKEN: changed" in event.detail
    assert SECRET_TOKEN not in event.detail
    assert SECRET_TOKEN not in event.target


def test_the_token_page_says_that_a_token_is_set(boss_client):
    page = boss_client.get(_url("telegram")).content.decode()
    assert "Not set" in page or "not set" in page

    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=SECRET_TOKEN))
    page = boss_client.get(_url("telegram")).content.decode()

    assert "Set" in page
    assert SECRET_TOKEN not in page


def test_an_empty_token_field_keeps_the_saved_token(boss_client):
    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=SECRET_TOKEN))

    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=""))

    assert conf.TELEGRAM_BOT_TOKEN == SECRET_TOKEN


def test_the_clear_box_removes_the_saved_token(boss_client):
    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_BOT_TOKEN=SECRET_TOKEN))

    boss_client.post(_url("telegram"), _telegram_values(reset__TELEGRAM_BOT_TOKEN="on"))

    assert not conf.is_saved("TELEGRAM_BOT_TOKEN")


def test_a_bad_chat_id_is_refused(boss_client):
    response = boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_CHAT_IDS="not an id"))

    assert response.status_code == 200
    assert not Setting.objects.filter(key="TELEGRAM_CHAT_IDS").exists()


def test_chat_ids_are_saved_as_a_list(boss_client):
    boss_client.post(_url("telegram"), _telegram_values(TELEGRAM_CHAT_IDS="123\n-1001234567890"))

    assert conf.TELEGRAM_CHAT_IDS == ["123", "-1001234567890"]


def test_the_telegram_page_has_the_test_buttons_for_a_superuser_only(
    boss_client, staff_client, offline
):
    check = reverse("ops:job_run", args=["telegram-check"])

    assert check in boss_client.get(_url("telegram")).content.decode()
    assert check not in staff_client.get(_url("telegram")).content.decode()


def test_a_saved_value_changes_the_config_page(boss_client):
    boss_client.post(_url("llm"), _llm_values(LLM_MODEL="visible-model-name"))

    assert "visible-model-name" in boss_client.get(reverse("ops:config")).content.decode()
