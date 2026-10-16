#!/bin/sh
set -eu

: "${MINIO_ROOT_USER:?Set MINIO_ROOT_USER in .env.dev or .env.prod}"
: "${MINIO_ROOT_PASSWORD:?Set MINIO_ROOT_PASSWORD in .env.dev or .env.prod}"

mc --config-dir /tmp/minio-client alias set storage http://minio:9000 \
  "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc --config-dir /tmp/minio-client mb --ignore-existing storage/kashengine-backups
mc --config-dir /tmp/minio-client mb --ignore-existing storage/kashengine-reports
