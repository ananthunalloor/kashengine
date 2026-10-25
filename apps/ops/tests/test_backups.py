"""Snapshot access control, fidelity, atomicity, and command coverage."""

import json
from io import StringIO

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from apps.api.models import ApiToken
from apps.companies.models import Company
from apps.ops import backups
from apps.ops.models import AuditEvent
from apps.siteconfig import conf
from apps.siteconfig.models import Setting

pytestmark = pytest.mark.django_db(transaction=True)


def _upload(payload):
    return SimpleUploadedFile("snapshot.json", payload, content_type="application/json")


def test_anonymous_cannot_access_backups(client):
    for name in ("backups", "backup_export", "backup_import"):
        response = client.get(reverse(f"ops:{name}"))
        assert response.status_code == 302
        assert "/login/" in response.url


@pytest.mark.parametrize("client_name", ["member_client", "staff_client"])
def test_only_superusers_can_access_any_backup_surface(request, client_name):
    client = request.getfixturevalue(client_name)
    assert client.get(reverse("ops:backups")).status_code == 403
    for name in ("backup_export", "backup_import"):
        assert client.post(reverse(f"ops:{name}")).status_code == 403


def test_controls_navigation_and_methods(boss_client, staff_client):
    page = boss_client.get(reverse("ops:backups"))
    assert page.status_code == 200
    assert b"RESTORE" in page.content
    assert "no-store" in page["Cache-Control"]
    assert reverse("ops:backups").encode() not in staff_client.get(reverse("ops:settings")).content
    for name in ("backup_export", "backup_import"):
        assert boss_client.get(reverse(f"ops:{name}")).status_code == 405


def test_both_actions_require_csrf(boss):
    client = Client(enforce_csrf_checks=True)
    client.force_login(boss)
    for name in ("backup_export", "backup_import"):
        assert client.post(reverse(f"ops:{name}")).status_code == 403


def test_round_trip_restores_records_relations_secrets_and_sequences(boss, django_user_model):
    group = Group.objects.create(name="Analysts")
    permission = Permission.objects.first()
    assert permission is not None
    group.permissions.add(permission)
    boss.groups.add(group)
    boss.user_permissions.add(permission)
    company = Company.objects.create(id=9999, symbol="ROUNDTRIP", name="Original")
    Setting.objects.create(key="TELEGRAM_BOT_TOKEN", value="encrypted-value", updated_by=boss)
    token = ApiToken.objects.create(user=boss, name="test", prefix="12345678", token_hash="a" * 64)
    interval = IntervalSchedule.objects.create(every=7, period="minutes")
    task = PeriodicTask.objects.create(name="snapshot-test", task="test.task", interval=interval)
    password = boss.password
    payload = backups.export_database(boss)
    snapshot = json.loads(payload)
    assert {model._meta.label_lower for model in backups._models()} == set(snapshot["models"])
    Company.objects.filter(pk=company.pk).update(name="Changed")
    Company.objects.create(symbol="DELETE", name="Not in backup")
    boss.groups.clear()
    token.delete()
    Setting.objects.all().delete()
    task.delete()

    count = backups.restore_database(payload, boss, confirmation="RESTORE")

    assert count == len(snapshot["records"])
    assert list(Company.objects.values_list("symbol", "name")) == [("ROUNDTRIP", "Original")]
    restored = django_user_model.objects.get(pk=boss.pk)
    assert restored.password == password
    assert list(restored.groups.values_list("name", flat=True)) == ["Analysts"]
    assert restored.user_permissions.filter(pk=permission.pk).exists()
    assert Group.objects.get(pk=group.pk).permissions.filter(pk=permission.pk).exists()
    assert Setting.objects.get(key="TELEGRAM_BOT_TOKEN").value == "encrypted-value"
    assert ApiToken.objects.get(prefix="12345678").user.pk == boss.pk
    assert PeriodicTask.objects.get(name="snapshot-test").interval.every == 7
    assert Company.objects.create(symbol="NEXT", name="Next").pk > 9999
    assert AuditEvent.objects.filter(action="restore database", actor_name="boss").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(version=999),
        lambda data: data.update(schema="wrong"),
        lambda data: data.update(models=[]),
        lambda data: data.update(records={}),
        lambda data: data["records"].append({"model": "unknown.model"}),
        lambda data: data["records"].append({"model": []}),
        lambda data: data["records"].append(data["records"][0]),
        lambda data: data["records"][0]["fields"].update(unknown="value"),
        lambda data: data["records"][0].pop("pk"),
    ],
)
def test_invalid_snapshot_does_not_change_database(boss, mutation):
    Company.objects.create(symbol="KEEP", name="Keep")
    snapshot = json.loads(backups.export_database(boss))
    mutation(snapshot)
    with pytest.raises(backups.BackupError):
        backups.restore_database(json.dumps(snapshot).encode(), boss, confirmation="RESTORE")
    assert Company.objects.filter(symbol="KEEP").exists()


@pytest.mark.parametrize("payload", [b"not JSON", b"\xff", b"[]"])
def test_unreadable_snapshot_is_rejected(boss, payload):
    with pytest.raises(backups.BackupError):
        backups.restore_database(payload, boss, confirmation="RESTORE")


def test_confirmation_and_size_limits(boss, monkeypatch):
    payload = backups.export_database(boss)
    with pytest.raises(backups.BackupError, match="Type RESTORE"):
        backups.restore_database(payload, boss, confirmation="")
    monkeypatch.setattr(backups, "MAX_BACKUP_BYTES", 10)
    with pytest.raises(backups.BackupError, match="limit"):
        backups.restore_database(payload, boss, confirmation="RESTORE")
    with pytest.raises(backups.BackupError, match="exceeds"):
        backups.export_database(boss)


def test_failed_restore_rolls_back_deleted_and_partially_loaded_rows(boss, monkeypatch):
    Company.objects.create(symbol="KEEP", name="Keep")
    payload = backups.export_database(boss)
    Company.objects.create(symbol="LATER", name="Later")

    def fail_constraints(*args, **kwargs):
        raise IntegrityError("Simulated broken foreign key")

    with monkeypatch.context() as patch:
        patch.setattr(backups.connection, "check_constraints", fail_constraints)
        with pytest.raises(backups.BackupError, match="no database records were changed"):
            backups.restore_database(payload, boss, confirmation="RESTORE")
    assert set(Company.objects.values_list("symbol", flat=True)) == {"KEEP", "LATER"}


def test_invalid_foreign_key_rolls_back(boss):
    Company.objects.create(symbol="KEEP", name="Keep")
    Setting.objects.create(key="LLM_MODEL", value='"model"', updated_by=boss)
    snapshot = json.loads(backups.export_database(boss))
    row = next(row for row in snapshot["records"] if row["model"] == "siteconfig.setting")
    row["fields"]["updated_by"] = 987654321
    with pytest.raises(backups.BackupError):
        backups.restore_database(json.dumps(snapshot).encode(), boss, confirmation="RESTORE")
    assert Company.objects.filter(symbol="KEEP").exists()
    updated_by = Setting.objects.get(key="LLM_MODEL").updated_by
    assert updated_by is not None
    assert updated_by.pk == boss.pk


def test_invalid_field_value_rolls_back_partial_load(boss):
    Company.objects.create(symbol="KEEP", name="Keep")
    snapshot = json.loads(backups.export_database(boss))
    row = next(row for row in snapshot["records"] if row["model"] == "companies.company")
    row["fields"]["created_at"] = "invalid date"
    with pytest.raises(backups.BackupError, match="no database records were changed"):
        backups.restore_database(json.dumps(snapshot).encode(), boss, confirmation="RESTORE")
    assert Company.objects.filter(symbol="KEEP").exists()
    boss.refresh_from_db()
    assert boss.is_superuser


def test_restore_invalidates_cached_settings(boss):
    setting = Setting.objects.create(key="LLM_MODEL", value='"snapshot-model"')
    payload = backups.export_database(boss)
    setting.value = '"changed-model"'
    setting.save()
    conf.invalidate()
    assert conf.LLM_MODEL == "changed-model"

    backups.restore_database(payload, boss, confirmation="RESTORE")

    assert conf.LLM_MODEL == "snapshot-model"


def test_restore_rejects_snapshot_without_active_superuser(boss):
    snapshot = json.loads(backups.export_database(boss))
    for row in snapshot["records"]:
        if row["model"] == "auth.user":
            row["fields"]["is_superuser"] = False
    with pytest.raises(backups.BackupError):
        backups.restore_database(json.dumps(snapshot).encode(), boss, confirmation="RESTORE")
    boss.refresh_from_db()
    assert boss.is_superuser


def test_service_rejects_non_superusers(member, staff, boss):
    payload = backups.export_database(boss)
    for actor in (member, staff):
        with pytest.raises(backups.BackupError, match="active superuser"):
            backups.export_database(actor)
        with pytest.raises(backups.BackupError, match="active superuser"):
            backups.restore_database(payload, actor, confirmation="RESTORE")
    boss.is_active = False
    with pytest.raises(backups.BackupError, match="active superuser"):
        backups.export_database(boss)


def test_browser_download_and_restore_signs_out_even_if_importer_is_absent(
    boss_client, boss, django_user_model
):
    Company.objects.create(symbol="KEEP", name="Keep")
    response = boss_client.post(reverse("ops:backup_export"))
    assert response.status_code == 200
    assert "attachment;" in response["Content-Disposition"]
    assert "no-store" in response["Cache-Control"]
    payload = b"".join(response.streaming_content)
    importer = django_user_model.objects.create_superuser("importer", password="temporary")
    boss_client.force_login(importer)
    Company.objects.create(symbol="LATER", name="Later")
    response = boss_client.post(
        reverse("ops:backup_import"), {"backup": _upload(payload), "confirmation": "RESTORE"}
    )
    assert response.status_code == 302
    assert response.url == reverse("web:login")
    assert not Company.objects.filter(symbol="LATER").exists()
    assert not django_user_model.objects.filter(pk=importer.pk).exists()
    assert "_auth_user_id" not in boss_client.session


def test_import_errors_are_visible_and_keep_session(boss_client):
    for data, message in [
        ({}, b"Choose a database snapshot"),
        ({"backup": _upload(b"bad"), "confirmation": "RESTORE"}, b"not a valid JSON"),
    ]:
        response = boss_client.post(reverse("ops:backup_import"), data, follow=True)
        assert message in response.content
        assert "_auth_user_id" in boss_client.session


def test_command_roundtrip_restricted_file_and_confirmation(boss, tmp_path):
    path = tmp_path / "snapshot.json"
    output = StringIO()
    call_command("database_snapshot", "export", str(path), username="boss", stdout=output)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(CommandError):
        call_command("database_snapshot", "export", str(path), username="boss", stdout=output)
    Company.objects.create(symbol="LATER", name="Later")
    with pytest.raises(CommandError, match="Type RESTORE"):
        call_command("database_snapshot", "import", str(path), username="boss", stdout=output)
    assert Company.objects.filter(symbol="LATER").exists()
    call_command(
        "database_snapshot", "import", str(path), username="boss", confirm="RESTORE", stdout=output
    )
    assert not Company.objects.exists()
    assert "Database restored" in output.getvalue()


@pytest.mark.parametrize("username", ["member", "staff", "missing"])
def test_command_rejects_non_superuser_identity(member, staff, tmp_path, username):
    with pytest.raises(CommandError, match="active superuser"):
        call_command("database_snapshot", "export", str(tmp_path / "out.json"), username=username)
