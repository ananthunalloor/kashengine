"""Portable, schema-matched database snapshots for superusers.

Writers must be stopped during export and restore. Environment secrets and files are not
included. Only SQLite and PostgreSQL support the transactional replacement used here.
"""

# Django exposes model metadata and the unfiltered manager through these public APIs.
# ruff: noqa: SLF001

import hashlib
import json
from itertools import chain

from cryptography.fernet import Fernet, InvalidToken
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management.color import no_style
from django.core.management.sql import sql_flush
from django.core.serializers.base import DeserializationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from apps.siteconfig import conf

from .models import AuditEvent

FORMAT = "kashengine-database"
VERSION = 1
MAX_BACKUP_BYTES = 100 * 1024 * 1024
MAX_BACKUP_FILE_BYTES = 140 * 1024 * 1024
ENCRYPTED_HEADER = b"KASHENGINE-ENCRYPTED-1\n"


class BackupError(ValueError):
    """An unsupported, invalid, or unsuccessful database snapshot operation."""


def backup_cipher() -> Fernet:
    """Require a separate, valid environment key for encrypted backup files.

    Returns:
        The authenticated encryption cipher.

    Raises:
        BackupError: The environment key is missing or invalid.
    """
    key = settings.BACKUP_ENCRYPTION_KEY
    if not key:
        raise BackupError("Set BACKUP_ENCRYPTION_KEY in the environment before enabling backups.")
    try:
        return Fernet(key.encode())
    except (ValueError, UnicodeError) as exc:
        raise BackupError("BACKUP_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_snapshot(payload: bytes) -> bytes:
    """Encrypt a portable snapshot with the key kept outside the database.

    Args:
        payload: Unencrypted JSON snapshot bytes.

    Returns:
        A versioned header followed by a Fernet token.
    """
    return ENCRYPTED_HEADER + backup_cipher().encrypt(payload)


def _decrypt_snapshot(payload: bytes) -> bytes:
    """Authenticate encrypted files, passing plain JSON through unchanged.

    Args:
        payload: Uploaded or downloaded backup file bytes.

    Returns:
        The unencrypted snapshot bytes.

    Raises:
        BackupError: The file is too large or cannot be authenticated.
    """
    if len(payload) > MAX_BACKUP_FILE_BYTES:
        raise BackupError("Backup file exceeds the 140 MiB limit.")
    if not payload.startswith(ENCRYPTED_HEADER):
        return payload
    try:
        return backup_cipher().decrypt(payload[len(ENCRYPTED_HEADER) :])
    except InvalidToken as exc:
        raise BackupError(
            "Backup authentication failed. Check the encryption key and file."
        ) from exc


def _models():
    """Return managed non-proxy models in deterministic serialization order."""
    return sorted(
        (model for model in apps.get_models() if model._meta.managed and not model._meta.proxy),
        key=lambda model: model._meta.label_lower,
    )


def _schema() -> str:
    """Fingerprint the model definitions and applied migrations, not the database backend.

    Returns:
        A SHA-256 fingerprint shared by compatible SQLite and PostgreSQL installations.
    """
    migrations = sorted(MigrationRecorder(connection).applied_migrations())
    models = [
        (
            model._meta.label_lower,
            [
                (
                    field.name,
                    field.get_internal_type(),
                    field.null,
                    field.primary_key,
                    field.unique,
                    field.max_length,
                    field.column,
                    field.remote_field.model._meta.label_lower if field.is_relation else None,
                )
                for field in model._meta.local_fields + model._meta.local_many_to_many
            ],
        )
        for model in _models()
    ]
    schema = json.dumps([migrations, models], sort_keys=True)
    return hashlib.sha256(schema.encode()).hexdigest()


def _check_backend() -> None:
    """Reject backends without a tested transactional replacement implementation.

    Raises:
        BackupError: The connection is not SQLite or PostgreSQL.
    """
    if connection.vendor not in {"sqlite", "postgresql"}:
        raise BackupError("Database snapshots support only SQLite and PostgreSQL.")


def _lock_tables() -> None:
    """Block concurrent writers until the surrounding snapshot transaction finishes."""
    if connection.vendor == "postgresql":
        tables = connection.introspection.django_table_names(only_existing=True)
        names = ", ".join(connection.ops.quote_name(name) for name in sorted(tables))
        with connection.cursor() as cursor:
            cursor.execute(f"LOCK TABLE {names} IN ACCESS EXCLUSIVE MODE")
    elif connection.vendor == "sqlite":
        # Reserve SQLite's writer lock before any reads to avoid a read/write upgrade race.
        with connection.cursor() as cursor:
            cursor.execute("UPDATE ops_auditevent SET actor_name = actor_name WHERE 1 = 0")


def require_superuser(actor) -> None:
    """Authorize interactive exports and the owner of an automated backup.

    Args:
        actor: The user authorizing the database operation.

    Raises:
        BackupError: The user is inactive or not a superuser.
    """
    if not actor.is_active or not actor.is_superuser:
        raise BackupError("An active superuser is required.")


def export_database(actor) -> bytes:
    """Export all managed models, including sessions, secrets, and explicit join tables.

    Args:
        actor: The active superuser authorizing the snapshot.

    Returns:
        A portable JSON snapshot containing schema metadata and all managed records.

    Raises:
        BackupError: The snapshot exceeds the supported size.
    """
    require_superuser(actor)
    _check_backend()
    with transaction.atomic():
        _lock_tables()
        rows = chain.from_iterable(
            model._base_manager.order_by(model._meta.pk.name).iterator() for model in _models()
        )
        records = json.loads(serializers.serialize("json", rows))
        payload = json.dumps(
            {
                "format": FORMAT,
                "version": VERSION,
                "created_at": timezone.now().isoformat(),
                "schema": _schema(),
                "models": [model._meta.label_lower for model in _models()],
                "records": records,
            }
        ).encode()
        if len(payload) > MAX_BACKUP_BYTES:
            raise BackupError("Snapshot exceeds 100 MiB. Use a native database backup instead.")
        AuditEvent.objects.create(
            actor=actor, actor_name=actor.get_username(), action="export database"
        )
    return payload


def _read_snapshot(payload: bytes):
    """Validate snapshot metadata and record shapes before modifying the database.

    Args:
        payload: Unencrypted JSON snapshot bytes.

    Returns:
        The validated serialized record list.

    Raises:
        BackupError: The format, schema, record shape, or size is invalid.
    """
    if len(payload) > MAX_BACKUP_BYTES:
        raise BackupError("Snapshot exceeds the 100 MiB limit.")
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BackupError("The uploaded file is not a valid JSON snapshot.") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or data.get("version") != VERSION:
        raise BackupError("Unsupported database snapshot format or version.")
    models = {model._meta.label_lower: model for model in _models()}
    if data.get("schema") != _schema() or data.get("models") != list(models):
        raise BackupError("Snapshot schema differs. Use the same code revision and migrations.")
    records = data.get("records")
    if not isinstance(records, list):
        raise BackupError("Snapshot records must be a list.")
    seen = set()
    for row in records:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("model"), str)
            or row["model"] not in models
        ):
            raise BackupError("Snapshot contains an unknown model.")
        model = models[row["model"]]
        fields = {
            field.name
            for field in model._meta.local_fields
            if field.serialize and not field.primary_key
        } | {
            field.name
            for field in model._meta.local_many_to_many
            if field.serialize and field.remote_field.through._meta.auto_created
        }
        if not isinstance(row.get("fields"), dict) or set(row["fields"]) != fields:
            raise BackupError("Snapshot contains missing or unknown fields.")
        key = (row["model"], str(row.get("pk")))
        if row.get("pk") is None or key in seen:
            raise BackupError("Snapshot contains missing or duplicate primary keys.")
        seen.add(key)
    return records


def restore_database(payload: bytes, actor, *, confirmation: str) -> int:
    """Replace all records atomically; preserve the current database on any failure.

    Args:
        payload: A plain JSON snapshot or authenticated encrypted snapshot.
        actor: The active superuser authorizing replacement.
        confirmation: Must be the literal RESTORE.

    Returns:
        The number of restored records, excluding the new restore audit event.

    Raises:
        BackupError: Confirmation, validation, decryption, or transactional loading failed.
    """
    require_superuser(actor)
    if confirmation != "RESTORE":
        raise BackupError("Type RESTORE to confirm replacement of the entire database.")
    _check_backend()
    actor_name = actor.get_username()
    records = _read_snapshot(_decrypt_snapshot(payload))
    models = _models()
    try:
        # SQLite needs foreign-key checks disabled before entering the transaction.
        with connection.constraint_checks_disabled(), transaction.atomic():
            _lock_tables()
            connection.ops.execute_sql_flush(sql_flush(no_style(), connection))
            for obj in serializers.deserialize("python", records):
                obj.save()
            connection.check_constraints()
            if not get_user_model().objects.filter(is_active=True, is_superuser=True).exists():
                raise BackupError("Snapshot must contain at least one active superuser.")
            with connection.cursor() as cursor:
                for statement in connection.ops.sequence_reset_sql(no_style(), models):
                    cursor.execute(statement)
            # The importing actor may not exist in the restored database.
            AuditEvent.objects.create(actor_name=actor_name, action="restore database")
            transaction.on_commit(conf.invalidate)
    except (DatabaseError, DeserializationError, ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, BackupError):
            raise
        raise BackupError("Restore failed; no database records were changed.") from exc
    return len(records)
