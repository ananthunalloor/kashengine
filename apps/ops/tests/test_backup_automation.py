"""Encrypted backups, destination settings, scheduling, and explicit failure behavior."""

import json
from datetime import UTC, datetime
from io import StringIO
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from cryptography.fernet import Fernet
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django_celery_beat.models import PeriodicTask

from apps.companies.models import Company
from apps.ops import backup_automation, backups, configview, schedule, tasks
from apps.ops.backup_forms import BackupConfigurationForm
from apps.ops.models import AuditEvent, BackupConfiguration, TaskRun
from apps.siteconfig import crypto

pytestmark = pytest.mark.django_db(transaction=True)

ACCESS_KEY = "test-access-key"
SECRET_KEY = "test-secret-key"


@pytest.fixture
def backup_key(settings):
    settings.BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    return settings.BACKUP_ENCRYPTION_KEY


def _values(**kwargs):
    return {
        "enabled": "on",
        "backup_time": "02:00",
        "timezone": "Asia/Kolkata",
        "destination": "local",
        "local_directory": "/backups",
        "prefix": "kashengine",
        **kwargs,
    }


def _config(boss, tmp_path):
    config = BackupConfiguration(pk=1, enabled=True, local_directory=str(tmp_path))
    backup_automation.save_configuration(config, boss)
    return config


def test_defaults_are_disabled_at_two_am():
    config = backup_automation.configuration()
    assert not config.enabled
    assert config.backup_time.hour == 2
    assert config.backup_time.minute == 0
    assert config.timezone == "Asia/Kolkata"
    assert not BackupConfiguration.objects.exists()


@pytest.mark.parametrize("name", ["backup_settings", "backup_run"])
def test_configuration_actions_require_superuser_post_and_csrf(
    name, boss, boss_client, staff_client, member_client, client
):
    url = reverse(f"ops:{name}")
    assert client.post(url).status_code == 302
    assert staff_client.post(url).status_code == 403
    assert member_client.post(url).status_code == 403
    assert boss_client.get(url).status_code == 405
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(boss)
    assert csrf_client.post(url).status_code == 403


def test_save_enable_change_time_and_disable(boss_client, backup_key):
    url = reverse("ops:backup_settings")
    assert boss_client.post(url, _values()).status_code == 302
    config = BackupConfiguration.objects.get(pk=1)
    entry = PeriodicTask.objects.get(name=backup_automation.SCHEDULE_NAME)
    assert config.enabled
    assert entry.enabled
    assert entry.task == backup_automation.TASK_NAME
    assert entry.crontab.hour == "2"
    assert entry.crontab.minute == "0"
    assert str(entry.crontab.timezone) == "Asia/Kolkata"
    assert entry.expire_seconds == 3600
    assert (
        boss_client.post(url, _values(backup_time="23:45", timezone="Europe/London")).status_code
        == 302
    )
    entry.refresh_from_db()
    assert entry.crontab.hour == "23"
    assert entry.crontab.minute == "45"
    assert str(entry.crontab.timezone) == "Europe/London"
    assert PeriodicTask.objects.filter(name=entry.name).count() == 1
    assert boss_client.post(url, _values(enabled="")).status_code == 302
    entry.refresh_from_db()
    config.refresh_from_db()
    assert not entry.enabled
    assert not config.enabled
    assert AuditEvent.objects.filter(action="configure database backups").count() == 3


def test_daily_schedule_uses_selected_local_time(boss, backup_key):
    form = BackupConfigurationForm(_values(backup_time="02:15", timezone="Asia/Kolkata"))
    assert form.is_valid()
    form.save_for(boss)
    now = datetime(2026, 1, 5, 21, 0, tzinfo=UTC)  # 02:30 on January 6 in Kolkata.
    assert schedule.next_run(backup_automation.TASK_NAME, now) == datetime(
        2026, 1, 6, 20, 45, tzinfo=UTC
    )  # 02:15 on January 7 in Kolkata.


def test_encryption_key_is_masked_by_config_display(backup_key):
    assert configview.display_value("BACKUP_ENCRYPTION_KEY", backup_key) == "set (hidden)"


def test_minio_endpoint_is_accepted_by_form_and_shared_validator(backup_key):
    form = BackupConfigurationForm(
        _values(
            destination="s3",
            bucket="kashengine-backups",
            endpoint_url="http://minio:9000",
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
        )
    )
    assert form.is_valid(), form.errors
    backup_automation.validate_s3_endpoint(form.cleaned_data["endpoint_url"])


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://minio:9000.evil.example",
        "http://minio:9000@evil.example",
        "http://minio:9001",
        "http://minio:9000?redirect=evil",
        "http://minio:9000/other",
        "http://localhost:9000",
        "http://storage.example.com",
    ],
)
def test_private_http_exception_cannot_be_used_for_other_endpoints(endpoint):
    with pytest.raises(backups.BackupError, match="Use HTTPS"):
        backup_automation.validate_s3_endpoint(endpoint)


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"timezone": "Not/AZone"}, "timezone"),
        ({"backup_time": "25:00"}, "backup_time"),
        ({"backup_time": "02:00:59"}, "backup_time"),
        ({"local_directory": "relative"}, "local_directory"),
        ({"endpoint_url": "http://storage.example.com"}, "endpoint_url"),
        ({"endpoint_url": "https://secret:password@storage.example.com"}, "endpoint_url"),
        ({"endpoint_url": "https://storage.example.com?secret=x"}, "endpoint_url"),
        ({"destination": "unsupported"}, "destination"),
        ({"destination": "s3", "bucket": ""}, "bucket"),
        ({"destination": "s3", "bucket": "backups"}, "access_key"),
    ],
)
def test_invalid_configuration(values, field, backup_key):
    form = BackupConfigurationForm(_values(**values))
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.parametrize("key", ["", "invalid"])
def test_missing_or_invalid_encryption_key_blocks_enable(boss_client, settings, key):
    settings.BACKUP_ENCRYPTION_KEY = key
    response = boss_client.post(reverse("ops:backup_settings"), _values())
    assert response.status_code == 400
    assert b"BACKUP_ENCRYPTION_KEY" in response.content
    assert not BackupConfiguration.objects.exists()


def test_can_disable_with_missing_key(boss_client, boss, tmp_path, settings):
    _config(boss, tmp_path)
    settings.BACKUP_ENCRYPTION_KEY = ""
    response = boss_client.post(reverse("ops:backup_settings"), _values(enabled=""))
    assert response.status_code == 302
    assert not BackupConfiguration.objects.get(pk=1).enabled


def test_s3_secrets_encrypted_kept_blank_and_never_rendered(boss_client, backup_key):
    values = _values(
        destination="s3",
        bucket="private-backups",
        endpoint_url="https://s3.example.com",
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
    )
    assert boss_client.post(reverse("ops:backup_settings"), values).status_code == 302
    config = BackupConfiguration.objects.get(pk=1)
    assert ACCESS_KEY not in config.access_key_encrypted
    assert SECRET_KEY not in config.secret_key_encrypted
    assert crypto.decrypt(config.access_key_encrypted) == ACCESS_KEY
    assert crypto.decrypt(config.secret_key_encrypted) == SECRET_KEY
    page = boss_client.get(reverse("ops:backups")).content.decode()
    assert ACCESS_KEY not in page
    assert SECRET_KEY not in page
    values.update(access_key="", secret_key="")
    assert boss_client.post(reverse("ops:backup_settings"), values).status_code == 302
    config.refresh_from_db()
    assert crypto.decrypt(config.secret_key_encrypted) == SECRET_KEY
    values.update(clear_credentials="on")
    assert boss_client.post(reverse("ops:backup_settings"), values).status_code == 400
    values.update(enabled="")
    assert boss_client.post(reverse("ops:backup_settings"), values).status_code == 302
    config.refresh_from_db()
    assert config.secret_key_encrypted == config.access_key_encrypted == ""


def test_local_task_encrypts_writes_restricted_file_and_restores(boss, tmp_path, backup_key):
    _config(boss, tmp_path)
    Company.objects.create(name="Original", symbol="ORIGINAL")

    result = tasks.backup_database.run()

    files = list(tmp_path.iterdir())
    assert len(files) == 1
    path = files[0]
    assert str(path) == result["location"]
    assert path.stat().st_mode & 0o777 == 0o600
    payload = path.read_bytes()
    assert len(payload) == result["bytes"]
    assert payload.startswith(backups.ENCRYPTED_HEADER)
    assert b"ORIGINAL" not in payload
    records = json.loads(Fernet(backup_key.encode()).decrypt(payload.split(b"\n", 1)[1]))
    assert records["format"] == backups.FORMAT
    Company.objects.create(name="Remove me", symbol="REMOVE")
    backups.restore_database(payload, boss, confirmation="RESTORE")
    assert list(Company.objects.values_list("symbol", flat=True)) == ["ORIGINAL"]


def test_missing_directory_and_write_failure_are_explicit(boss, backup_key, tmp_path, monkeypatch):
    config = _config(boss, tmp_path)
    config.local_directory = str(tmp_path / "does-not-exist")
    config.save()
    with pytest.raises(backups.BackupError, match="existing absolute directory"):
        backup_automation.run_backup()
    config.local_directory = str(tmp_path)
    config.save()
    with monkeypatch.context() as patch:
        patch.setattr(backup_automation.os, "fsync", Mock(side_effect=OSError("disk full")))
        with pytest.raises(backups.BackupError, match="Local backup failed"):
            backup_automation.run_backup()
    assert list(tmp_path.iterdir()) == []
    assert not AuditEvent.objects.filter(action="store database backup").exists()


def test_completed_and_failed_backups_are_visible_in_run_history(
    boss, boss_client, tmp_path, backup_key
):
    config = _config(boss, tmp_path)
    result = tasks.backup_database.apply()
    run = TaskRun.objects.get(task_id=result.id)
    assert run.status == TaskRun.Status.SUCCESS
    assert ".json.enc" in run.result
    page = boss_client.get(reverse("ops:backups"))
    assert reverse("ops:run", args=[run.pk]).encode() in page.content
    config.enabled = False
    config.save()
    result = tasks.backup_database.apply()
    run = TaskRun.objects.get(task_id=result.id)
    assert run.status == TaskRun.Status.FAILURE
    assert "disabled" in run.error


def test_s3_uses_configured_endpoint_region_prefix_and_encrypted_payload(
    boss, tmp_path, backup_key, monkeypatch
):
    config = _config(boss, tmp_path)
    config.destination = "s3"
    config.bucket = "private-backups"
    config.prefix = "database/daily/"
    config.endpoint_url = "https://s3.example.com"
    config.region = "custom-region"
    config.access_key_encrypted = crypto.encrypt(ACCESS_KEY)
    config.secret_key_encrypted = crypto.encrypt(SECRET_KEY)
    config.save()
    # Botocore's real request validator checks the request shape without making a network call.
    client = backup_automation.boto3.client(
        "s3",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="custom-region",
        endpoint_url=config.endpoint_url,
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr(backup_automation.boto3, "client", factory)
    with Stubber(client) as stub:
        stub.add_response("put_object", {"ETag": '"test-etag"'})
        result = backup_automation.run_backup()
        stub.assert_no_pending_responses()
    kwargs = factory.call_args.kwargs
    assert kwargs["endpoint_url"] == config.endpoint_url
    assert kwargs["region_name"] == "custom-region"
    assert kwargs["aws_access_key_id"] == ACCESS_KEY
    assert kwargs["aws_secret_access_key"] == SECRET_KEY
    assert kwargs["config"].s3 == {"addressing_style": "path"}
    assert result["location"].startswith("s3://private-backups/database/daily/kashengine-")
    assert result["location"].endswith(".json.enc")


def test_s3_upload_failure_is_not_success_and_hides_provider_details(
    boss, tmp_path, backup_key, monkeypatch
):
    config = _config(boss, tmp_path)
    config.destination = "s3"
    config.bucket = "bucket"
    config.access_key_encrypted = crypto.encrypt(ACCESS_KEY)
    config.secret_key_encrypted = crypto.encrypt(SECRET_KEY)
    config.save()
    client = Mock()
    client.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": SECRET_KEY}}, "PutObject"
    )
    monkeypatch.setattr(backup_automation.boto3, "client", Mock(return_value=client))
    with pytest.raises(backups.BackupError, match="S3 backup upload failed") as exc:
        backup_automation.run_backup()
    assert SECRET_KEY not in str(exc.value)
    assert exc.value.__suppress_context__
    client.close.assert_called_once()
    assert not AuditEvent.objects.filter(action="store database backup").exists()


def test_disabled_queued_task_and_demoted_owner_cannot_back_up(boss, tmp_path, backup_key):
    with pytest.raises(backups.BackupError, match="disabled"):
        tasks.backup_database.run()
    _config(boss, tmp_path)
    boss.is_superuser = False
    boss.save()
    with pytest.raises(backups.BackupError, match="active superuser"):
        tasks.backup_database.run()
    assert list(tmp_path.iterdir()) == []


def test_deleted_owner_cannot_run_backup(boss, tmp_path, backup_key):
    _config(boss, tmp_path)
    boss.delete()
    with pytest.raises(backups.BackupError, match="active superuser"):
        backup_automation.run_backup()
    assert list(tmp_path.iterdir()) == []


def test_manual_run_queues_worker_and_disabled_run_is_refused(
    boss_client, boss, queue, backup_key, tmp_path
):
    url = reverse("ops:backup_run")
    assert boss_client.post(url).status_code == 302
    assert queue == []
    _config(boss, tmp_path)
    assert boss_client.post(url).status_code == 302
    assert len(queue) == 1
    assert queue[0][0] == backup_automation.TASK_NAME
    assert boss_client.post(url).status_code == 302
    assert len(queue) == 1


def test_encrypted_import_supports_browser_and_command(boss, boss_client, backup_key, tmp_path):
    path = tmp_path / "backup.json.enc"
    call_command(
        "database_snapshot", "export", str(path), username="boss", encrypt=True, stdout=StringIO()
    )
    assert path.read_bytes().startswith(backups.ENCRYPTED_HEADER)
    call_command(
        "database_snapshot",
        "import",
        str(path),
        username="boss",
        confirm="RESTORE",
        stdout=StringIO(),
    )
    response = boss_client.post(
        reverse("ops:backup_import"),
        {
            "backup": SimpleUploadedFile("backup.json.enc", path.read_bytes()),
            "confirmation": "RESTORE",
        },
    )
    assert response.url == reverse("web:login")
    assert "_auth_user_id" not in boss_client.session


def test_schedule_is_managed_only_on_backups_page(boss_client, boss, tmp_path):
    _config(boss, tmp_path)
    entry = PeriodicTask.objects.get(name=backup_automation.SCHEDULE_NAME)
    page = boss_client.get(reverse("ops:schedule"))
    assert b"Manage backups" in page.content
    assert backup_automation.TASK_NAME not in schedule.schedulable_tasks()
    for route in ("schedule_edit", "schedule_toggle", "schedule_delete"):
        response = boss_client.post(reverse(f"ops:{route}", args=[entry.pk]), {})
        assert response.url == reverse("ops:backups")
        entry.refresh_from_db()
        assert entry.enabled
        assert entry.task == backup_automation.TASK_NAME
    boss_client.post(reverse("ops:schedule_reset"), {"confirm": "yes"})
    entry.refresh_from_db()
    assert entry.enabled


def test_wrong_key_or_tampered_ciphertext_cannot_replace_data(boss, backup_key, settings):
    Company.objects.create(symbol="KEEP", name="Keep")
    payload = backups.encrypt_snapshot(backups.export_database(boss))
    with pytest.raises(backups.BackupError, match="authentication failed"):
        backups.restore_database(payload[:-12] + b"tampered", boss, confirmation="RESTORE")
    settings.BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    with pytest.raises(backups.BackupError, match="authentication failed"):
        backups.restore_database(payload, boss, confirmation="RESTORE")
    assert Company.objects.filter(symbol="KEEP").exists()
