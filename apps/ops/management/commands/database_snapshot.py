"""Export or restore the database as an explicitly identified superuser."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.ops.backups import (
    MAX_BACKUP_FILE_BYTES,
    BackupError,
    encrypt_snapshot,
    export_database,
    restore_database,
)


class Command(BaseCommand):
    """Share the Ops snapshot format with trusted server operators."""

    help = (
        "Export or replace all database records. Requires an existing active superuser. "
        "Stop database writers first. Environment keys and files are not included."
    )

    def add_arguments(self, parser):
        """Require an operation, file, and superuser identity.

        Args:
            parser: Django's command argument parser.
        """
        parser.add_argument("operation", choices=["export", "import"])
        parser.add_argument("file", type=Path)
        parser.add_argument("--username", required=True, help="Existing active superuser username.")
        parser.add_argument("--confirm", default="", help="Type RESTORE for a replacement import.")
        parser.add_argument(
            "--encrypt", action="store_true", help="Encrypt the export with BACKUP_ENCRYPTION_KEY."
        )

    def handle(self, *args, **options):
        """Read/write a bounded snapshot; never overwrite an existing export file.

        Args:
            *args: Unused positional command arguments.
            **options: Parsed operation, path, identity, and encryption/confirmation options.

        Raises:
            CommandError: Authorization, storage, or snapshot processing failed.
        """
        actor = (
            get_user_model()
            .objects.filter(username=options["username"], is_active=True, is_superuser=True)
            .first()
        )
        if actor is None:
            raise CommandError("An existing active superuser is required.")
        path = options["file"]
        try:
            if options["operation"] == "export":
                payload = export_database(actor)
                if options["encrypt"]:
                    payload = encrypt_snapshot(payload)
                with path.open("xb") as output:
                    path.chmod(0o600)
                    output.write(payload)
                self.stdout.write(self.style.SUCCESS("Database snapshot exported. Keep it secure."))
            else:
                with path.open("rb") as source:
                    payload = source.read(MAX_BACKUP_FILE_BYTES + 1)
                count = restore_database(payload, actor, confirmation=options["confirm"])
                self.stdout.write(self.style.SUCCESS(f"Database restored: {count} records."))
        except (OSError, BackupError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
