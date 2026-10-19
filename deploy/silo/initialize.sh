#!/bin/sh
set -eu

: "${MINIO_ROOT_USER:?Set MINIO_ROOT_USER in .env.dev or .env.prod}"
: "${MINIO_ROOT_PASSWORD:?Set MINIO_ROOT_PASSWORD in .env.dev or .env.prod}"

mc --config-dir /tmp/silo-client alias set storage http://silo:9000 \
  "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc --config-dir /tmp/silo-client mb --ignore-existing storage/kashengine-backups
mc --config-dir /tmp/silo-client mb --ignore-existing storage/kashengine-reports
