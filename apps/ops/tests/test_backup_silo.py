"""Opt-in end-to-end verification against an isolated, initialized Silo test service."""

import os
from unittest.mock import patch

import boto3
import httpx
import pytest
from botocore.config import Config
from cryptography.fernet import Fernet

from apps.companies.models import Company
from apps.ops import backup_automation, backups
from apps.ops.models import BackupConfiguration
from apps.siteconfig import crypto

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        not os.environ.get("TEST_BACKUP_SILO_ENDPOINT"),
        reason="Set TEST_BACKUP_SILO_ENDPOINT for an isolated, initialized Silo test service.",
    ),
]


def test_real_silo_encrypted_backup_private_buckets_and_restore(boss, settings):
    endpoint = os.environ["TEST_BACKUP_SILO_ENDPOINT"]
    access = os.environ["TEST_BACKUP_SILO_ACCESS_KEY"]
    secret = os.environ["TEST_BACKUP_SILO_SECRET_KEY"]
    settings.BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode()
    storage = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    try:
        assert {"kashengine-backups", "kashengine-reports"} <= {
            bucket["Name"] for bucket in storage.list_buckets()["Buckets"]
        }
        config = BackupConfiguration(
            pk=1,
            enabled=True,
            destination="s3",
            endpoint_url="http://silo:9000",
            bucket="kashengine-backups",
            prefix="integration",
            access_key_encrypted=crypto.encrypt(access),
            secret_key_encrypted=crypto.encrypt(secret),
        )
        backup_automation.save_configuration(config, boss)
        Company.objects.create(symbol="SILO", name="Silo test company")
        # Only transport is redirected to the test server's loopback-published port.
        factory = boto3.client

        def connect(service, **kwargs):
            assert kwargs["endpoint_url"] == "http://silo:9000"
            assert kwargs["config"].s3 == {"addressing_style": "path"}
            return factory(service, **{**kwargs, "endpoint_url": endpoint})

        with patch.object(backup_automation.boto3, "client", connect):
            result = backup_automation.run_backup()
        key = result["location"].removeprefix("s3://kashengine-backups/")
        response = storage.get_object(Bucket="kashengine-backups", Key=key)
        with response["Body"] as body:
            encrypted = body.read()
        assert encrypted.startswith(backups.ENCRYPTED_HEADER)
        assert b"Silo test company" not in encrypted
        assert response["ContentType"] == "application/octet-stream"
        assert httpx.get(f"{endpoint}/kashengine-backups/{key}", timeout=10).status_code == 403
        assert httpx.get(f"{endpoint}/kashengine-reports/", timeout=10).status_code == 403
        Company.objects.create(symbol="REMOVE", name="Remove")
        backups.restore_database(encrypted, boss, confirmation="RESTORE")
        assert list(Company.objects.values_list("symbol", flat=True)) == ["SILO"]
    finally:
        storage.close()
