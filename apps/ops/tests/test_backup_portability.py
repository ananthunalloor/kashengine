"""Opt-in real SQLite -> PostgreSQL -> SQLite recovery test.

TEST_BACKUP_POSTGRES_URL must name a test server whose role may create databases.
The test creates and drops only its own uniquely named database.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg import sql

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = """
import os
import sys
from pathlib import Path
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from apps.api.models import ApiToken
from apps.companies.models import Company
from apps.ops import backups
from apps.ops.models import BackupConfiguration
from apps.siteconfig import crypto
from apps.siteconfig.models import Setting

mode, source, target = sys.argv[1:]
call_command("migrate", verbosity=0)
User = get_user_model()
actor = User.objects.create_superuser("temporary-operator", password="temporary")
if mode == "seed":
    group = Group.objects.create(name="Investors")
    actor.groups.add(group)
    Company.objects.create(
        id=43210, name="Portable company", symbol="PORTABLE",
        screener_data={"price": 123.45, "unicode": "\\u20b9", "items": [1, None, True]},
    )
    Setting.objects.create(
        key="TELEGRAM_BOT_TOKEN", value=crypto.encrypt("portable-secret"), updated_by=actor
    )
    BackupConfiguration.objects.create(
        pk=1, enabled=False, configured_by=actor, timezone="Asia/Kolkata"
    )
    ApiToken.objects.create(
        user=actor, prefix="abcdefgh", token_hash="f" * 64, name="Portable"
    )
    interval = IntervalSchedule.objects.create(every=5, period="minutes")
    PeriodicTask.objects.create(name="portable", task="test.portable", interval=interval)
else:
    backups.restore_database(Path(source).read_bytes(), actor, confirmation="RESTORE")
    actor = User.objects.get(username="temporary-operator")
    assert actor.check_password("temporary")
    assert list(actor.groups.values_list("name", flat=True)) == ["Investors"]
    company = Company.objects.get(pk=43210)
    assert company.screener_data == {
        "price": 123.45, "unicode": "\\u20b9", "items": [1, None, True]
    }
    assert crypto.decrypt(Setting.objects.get(key="TELEGRAM_BOT_TOKEN").value) == "portable-secret"
    assert ApiToken.objects.get(prefix="abcdefgh").user_id == actor.pk
    assert BackupConfiguration.objects.get(pk=1).configured_by_id == actor.pk
    assert PeriodicTask.objects.get(name="portable").interval.every == 5
    created = Company.objects.create(name="Sequence check", symbol="SEQUENCE")
    assert created.pk > 43210
    created.delete()
Path(target).write_bytes(backups.encrypt_snapshot(backups.export_database(actor)))
print("verified " + connection.vendor)
"""


@pytest.mark.skipif(
    not os.environ.get("TEST_BACKUP_POSTGRES_URL"),
    reason="Set TEST_BACKUP_POSTGRES_URL for a disposable PostgreSQL test server.",
)
def test_encrypted_sqlite_postgres_sqlite_round_trip(tmp_path):
    server = os.environ["TEST_BACKUP_POSTGRES_URL"]
    name = f"kashbackup_test_{uuid.uuid4().hex}"
    parts = urlsplit(server)
    target_url = urlunsplit(parts._replace(path=f"/{name}"))
    env = {
        **os.environ,
        "BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "DJANGO_SECRET_KEY": "portability-test-key",
        "SETTINGS_ENCRYPTION_KEY": "portability-test-settings-key",
        "DJANGO_LOG_TO_FILE": "false",
        "TELEGRAM_BOT_TOKEN": "",
    }

    def run(mode, database, source, target, expected):
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", SCRIPT, mode, str(source), str(target)],
            cwd=ROOT,
            env={**env, "DATABASE_URL": database},
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert f"verified {expected}" in result.stdout

    with psycopg.connect(server, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            first = tmp_path / "sqlite.json.enc"
            second = tmp_path / "postgres.json.enc"
            final = tmp_path / "returned.json.enc"
            run("seed", f"sqlite:///{tmp_path / 'source.sqlite3'}", "-", first, "sqlite")
            run("restore", target_url, first, second, "postgresql")
            run("restore", f"sqlite:///{tmp_path / 'target.sqlite3'}", second, final, "sqlite")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
