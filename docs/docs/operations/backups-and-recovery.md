---
title: Backups and recovery
---

# Backups and recovery

A deployment is not operationally complete until a backup can be restored. Select a protected backup target before relying on production data. Store backups away from the host that runs the application, restrict access, and encrypt them at rest and in transit.

## State that needs protection

- PostgreSQL data: articles, sentiment results, company and IPO records, market quotes and predictions, reports, runtime settings, schedules, feeds, instruments, user records, task runs, login events, and audit history.
- The Django and settings encryption keys needed to read stored encrypted configuration. Store these separately from the database backup with an appropriate access policy.
- `caddy_data`, if preserving current certificate state is required. It contains sensitive certificate keys.
- The Ollama volume if the downloaded model needs to be preserved and model download time or bandwidth is significant. Models may be re-downloaded if their version and source remain available.
- Any deployment-specific media or uploaded files, if the current application begins storing them.
- The exact source revision, container image references, and `.env.prod` schema/version needed to reconstruct the deployment. Never put a plaintext `.env.prod` inside a general backup archive.

## Create a PostgreSQL backup

Create a protected backup directory that is excluded from Git. This example writes a PostgreSQL custom-format dump to a local path; move it to your chosen off-host destination after verifying it:

```bash
umask 077
mkdir -p backups
backup_file="backups/kashengine-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T db sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$backup_file"
```

Protect the backup from other local users. Do not commit it or print it to a log. Upload it to the backup target using an encrypted transport and verify the remote object size/checksum.

## Restore drill

Perform the restore in an isolated environment first. A restore can replace live records, so do not run it against production without a documented maintenance window and explicit approval.

A typical restore sequence is:

1. Stop web writes, Celery worker, and Beat for the target environment.
2. Confirm that the target database and backup belong to the expected environment and date.
3. Restore into a new/empty database using `pg_restore` with the correct owner and database settings.
4. Run Django migration checks and any post-restore integrity checks.
5. Start the application services and validate health, login, schedule rows, settings access, recent reports, and task execution.
6. Record the restore duration, errors, missing external dependencies, and any manual steps.

The exact database role and ownership options depend on the target environment. Review `docker-compose.prod.yml` and the database configuration before applying a destructive restore command.

## Recovery considerations

- If `SETTINGS_ENCRYPTION_KEY` is lost or changed, encrypted settings may be unreadable even when the database restores correctly. Recover the matching key or plan to re-enter those secrets.
- If `DJANGO_SECRET_KEY` changes without a separate settings encryption key, encrypted settings may become unreadable.
- Restore database data and compatible application code together. Schema compatibility matters.
- Caddy certificate state is not a substitute for certificate/key backup policy; Caddy may be able to issue a new certificate, subject to provider limits.
- A model download is not a data backup. Record which model and tag the application expects.

## Required operational decisions

Choose a backup target, retention period, recovery point objective, recovery time objective, encryption policy, and owner. Schedule automated backups only after a restore drill has succeeded. Monitor backup age and alert on failed or missing backups.
