"""Encrypted scheduled snapshots delivered by workers to S3 or a mounted folder."""

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.siteconfig import crypto

from . import backups
from .models import AuditEvent, BackupConfiguration

TASK_NAME = "ops.backup_database"
SCHEDULE_NAME = "automated-database-backup"
MINIO_ENDPOINT = "http://minio:9000"


def validate_s3_endpoint(value: str) -> None:
    """Allow HTTPS storage and only the bundled MinIO endpoint over private HTTP.

    Args:
        value: An endpoint URL, or empty for Amazon S3.

    Raises:
        backups.BackupError: The endpoint is insecure or contains URL credentials/query data.
    """
    if not value or value == MINIO_ENDPOINT:
        return
    try:
        URLValidator(schemes=["https"])(value)
        parsed = urlsplit(value)
    except (ValueError, ValidationError) as exc:
        raise backups.BackupError(
            "Use HTTPS with a valid URL and port, or http://minio:9000 for bundled MinIO."
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise backups.BackupError(
            "Use HTTPS without URL credentials or query, or http://minio:9000 for bundled MinIO."
        )


def configuration() -> BackupConfiguration:
    """Return the saved singleton, or an unsaved disabled default.

    Returns:
        The current backup configuration.
    """
    return BackupConfiguration.objects.filter(pk=1).first() or BackupConfiguration(pk=1)


def save_configuration(config: BackupConfiguration, actor) -> None:
    """Save the settings and the corresponding daily Beat schedule together.

    Args:
        config: Validated configuration to store as the singleton.
        actor: The active superuser authorizing future backups.
    """
    backups.require_superuser(actor)
    with transaction.atomic():
        config.pk = 1
        config.configured_by = actor
        config.save()
        cron, _created = CrontabSchedule.objects.get_or_create(
            minute=str(config.backup_time.minute),
            hour=str(config.backup_time.hour),
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone=config.timezone,
        )
        PeriodicTask.objects.update_or_create(
            name=SCHEDULE_NAME,
            defaults={
                "task": TASK_NAME,
                "enabled": config.enabled,
                "crontab": cron,
                "interval": None,
                "solar": None,
                "clocked": None,
                "last_run_at": None,
                "args": "[]",
                "kwargs": "{}",
                "expires": None,
                "expire_seconds": 3600,
            },
        )
        AuditEvent.objects.create(
            actor=actor, actor_name=actor.get_username(), action="configure database backups"
        )


def _credential(value: str) -> str:
    """Decrypt a saved S3 credential without falling back to an ambient identity.

    Args:
        value: The settings-key-encrypted credential.

    Returns:
        The decrypted credential.

    Raises:
        backups.BackupError: The credential is missing or unreadable.
    """
    result = crypto.decrypt(value)
    if not result:
        raise backups.BackupError("Saved S3 credentials cannot be read. Enter them again.")
    return result


def _upload_s3(config: BackupConfiguration, name: str, payload: bytes) -> str:
    """Upload an encrypted snapshot using bounded SDK timeouts and retries.

    Args:
        config: The validated S3 destination and encrypted credentials.
        name: A unique timestamped file name.
        payload: The encrypted snapshot bytes.

    Returns:
        The uploaded object's S3 URI.

    Raises:
        backups.BackupError: Destination validation or the upload failed.
    """
    if not config.bucket:
        raise backups.BackupError("Configure an S3 bucket before running a backup.")
    validate_s3_endpoint(config.endpoint_url)
    key = "/".join(part for part in (config.prefix.strip("/"), name) if part)
    try:
        client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url or None,
            region_name=config.region or "us-east-1",
            aws_access_key_id=_credential(config.access_key_encrypted),
            aws_secret_access_key=_credential(config.secret_key_encrypted),
            config=Config(
                s3={"addressing_style": "path"} if config.endpoint_url else None,
                connect_timeout=10,
                read_timeout=60,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        try:
            client.put_object(
                Bucket=config.bucket,
                Key=key,
                Body=payload,
                ContentType="application/octet-stream",
            )
        finally:
            client.close()
    except (BotoCoreError, ClientError):
        # Provider errors may contain signed URLs or credentials.
        raise backups.BackupError(
            "S3 backup upload failed. Check credentials and bucket access."
        ) from None
    return f"s3://{config.bucket}/{key}"


def _write_local(config: BackupConfiguration, name: str, payload: bytes) -> str:
    """Publish a complete, private encrypted file in an existing mounted directory.

    Args:
        config: The configured absolute worker-side directory.
        name: A unique timestamped file name.
        payload: The encrypted snapshot bytes.

    Returns:
        The completed backup file path.

    Raises:
        backups.BackupError: The directory is unavailable or writing failed.
    """
    directory = Path(config.local_directory)
    if not directory.is_absolute() or not directory.is_dir():
        raise backups.BackupError("The backup directory must be an existing absolute directory.")
    target = directory / name
    temporary = directory / f".{name}.partial"
    created = False
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.rename(target)
    except OSError:
        raise backups.BackupError(
            "Local backup failed. Check the worker's mount and permissions."
        ) from None
    finally:
        if created:
            temporary.unlink(missing_ok=True)
    return str(target)


def run_backup() -> dict:
    """Deliver one encrypted snapshot; disabled or failed jobs never report success.

    Returns:
        The storage location and encrypted byte count.

    Raises:
        backups.BackupError: Backups are disabled, unauthorized, or misconfigured.
    """
    config = configuration()
    if not config.enabled:
        raise backups.BackupError("Automated backups are disabled.")
    if config.configured_by is None:
        raise backups.BackupError("Save backup settings as an active superuser before running.")
    # Validate the key before spending time reading the database.
    backups.backup_cipher()
    payload = backups.encrypt_snapshot(backups.export_database(config.configured_by))
    name = f"kashengine-{timezone.now():%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}.json.enc"
    if config.destination == BackupConfiguration.Destination.S3:
        location = _upload_s3(config, name, payload)
    elif config.destination == BackupConfiguration.Destination.LOCAL:
        location = _write_local(config, name, payload)
    else:
        raise backups.BackupError("Unknown backup destination.")
    AuditEvent.objects.create(
        actor_name=config.configured_by.get_username(),
        action="store database backup",
        detail=location,
    )
    return {"location": location, "bytes": len(payload)}
