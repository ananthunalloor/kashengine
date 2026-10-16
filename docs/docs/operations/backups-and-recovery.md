---
title: Backups and recovery
sidebar_label: Backups and recovery
description: What to back up, how to make a PostgreSQL backup, and how to test a restore.
---

# Backups and recovery

A backup has value only when you have tested a restore. Keep backups off the host that runs the
application. Restrict access to them and encrypt them.

## What to protect

| Item | Why | Where |
| --- | --- | --- |
| PostgreSQL data | All records: news, scores, companies, IPOs, quotes, predictions, reports, users, API token hashes, settings, schedule, feeds, instruments, task runs, login events, audit events | Volume `postgres_data` |
| `DJANGO_SECRET_KEY` and `SETTINGS_ENCRYPTION_KEY` | They decrypt the secrets that are saved on the dashboard (the Telegram bot token) | `.env.prod` |
| `.env.prod` | All first values and the secrets | The server |
| `minio_data` | Object storage data; MinIO admin credentials are in the shared environment file | Named volume |
| `caddy_data` | TLS keys and certificates. Optional: Caddy can get new ones. | Volume `caddy_data` |
| `ollama_data` | Downloaded models. Optional: you can download them again. | Volume `ollama_data` |
| Source revision | The code must match the database schema | Git |

Redis has no volume and holds no data that you must keep. It holds the Celery queue and the API
rate-limit counters. After a restart the queue is empty and the counters start again from zero.
The Beat schedule is in the database, so a restore brings it back.

Store the keys apart from the database backup. Never put a plain `.env.prod` in a general backup
archive.

## Superuser database snapshots

**Ops > Backups** provides download and upload controls only for superusers. Ordinary users and
staff cannot open the page, download a snapshot, or restore one. Both actions require a CSRF-protected
POST and are audited. A successful restore records the importing username even if that account is
not present in the snapshot.

Snapshots are versioned JSON files containing **all managed database records**, including users,
password hashes, permissions, subscriptions, sessions, API token hashes, encrypted settings, feeds,
instruments, schedules, task history, and application content. Relationships and primary keys are
preserved. Migration history is checked for compatibility, not replaced. Manual browser downloads
are unencrypted JSON; automated backups are always authenticated and encrypted. Treat both formats
as sensitive, restrict access, and never commit them.

This feature supports SQLite and PostgreSQL. It can populate a freshly migrated installation or
replace an existing installation's data. It is **not a merge**: all current records are deleted,
then the snapshot is loaded in one transaction. Invalid formats, different schemas, missing fields,
duplicate keys, invalid relationships, and snapshots without an active superuser are rejected.
Failed restores roll back the database changes. Imports accept only this application's snapshot
format (plain JSON or encrypted `.json.enc`), not arbitrary Django fixtures, CSV, SQL, or native
PostgreSQL dumps.

### Moving between SQLite and PostgreSQL

The snapshot format is database-independent. Export from SQLite and import into PostgreSQL, or
export from PostgreSQL and import into SQLite. This is also how you can populate production with
development data, or copy production data into a restricted development installation.

1. Use the same source revision and run all migrations on the target database.
2. Set the target `DATABASE_URL` for SQLite or PostgreSQL as appropriate. Copy the original
   `DJANGO_SECRET_KEY` and `SETTINGS_ENCRYPTION_KEY` securely if you need saved secrets and sessions
   to remain usable. Set `BACKUP_ENCRYPTION_KEY` too when importing an encrypted file.
3. Create a temporary target superuser (`python manage.py createsuperuser`).
4. Restore with the Ops upload or management command. The temporary user's data is replaced.
5. Check settings, counts, relationships, and login. The restore resets ID sequences so new
   records do not collide with imported primary keys.

**Before starting workers or Beat on the target**, review restored backup settings and scheduled
jobs. A copied production schedule can send real messages or upload to the production bucket.
Disable automated backups or select a separate destination for development. Do not put production
user data or credentials into an untrusted development environment.

### Download or restore in Ops

1. Plan a maintenance window for restores. Stop Celery workers, Beat, and other database writers,
   and prevent other users from changing data. Keep the web service available only for the operator.
2. Sign in as a superuser and open **Ops > Backups**.
3. Download a fresh snapshot before replacing any data.
4. To restore, choose a trusted snapshot, type **RESTORE**, and submit **Replace entire database**.
   The importing browser is signed out after success; sign in using an account from the snapshot.
5. Restart the web service, workers, and Beat to discard cached settings. Check the restored
   settings, schedules, content, accounts, and a manual job before reopening access.

The application limit is **100 MiB** of JSON. Encrypted uploads can be up to **140 MiB**, allowing
for encryption overhead. The supplied Caddy configuration allows 141 MiB on this upload path for
multipart overhead; other forms keep their 2 MB limit.
Reload Caddy after deploying this configuration change. Existing proxy/upload and worker timeouts
still apply: use the command line if a browser operation times out, and check the audit trail before
retrying a restore. For larger databases, use the native PostgreSQL procedure below.

### Management command

The same format is available from the server:

```bash
python manage.py database_snapshot export /secure/backups/kashengine.json --username admin
python manage.py database_snapshot import /secure/backups/kashengine.json --username admin --confirm RESTORE
# Optional encrypted manual export (requires BACKUP_ENCRYPTION_KEY):
python manage.py database_snapshot export /secure/backups/kashengine.json.enc --username admin --encrypt
python manage.py database_snapshot import /secure/backups/kashengine.json.enc --username admin --confirm RESTORE
```

Use your normal Python environment or run these commands in a one-off application container with
`docker compose run --rm --no-deps web python manage.py ...` (include your usual environment and
Compose file flags). Mount a restricted backup directory so the file persists outside the
container. Stop the web service as well as workers and Beat for command-line restores.

The command requires an existing **active superuser**. On a new installation, run migrations and
`createsuperuser` first; this temporary account will be replaced during import. The `--username`
argument identifies the operator, not password authentication: management commands require trusted
server-shell access, which already grants direct database access. Export files are created with
mode `0600`, and existing files are never overwritten.

Keep the same source revision, applied migrations, `DJANGO_SECRET_KEY`, and
`SETTINGS_ENCRYPTION_KEY` on the restore target. Snapshots do **not** include environment files,
keys, certificates, external files, Redis queues, or downloaded models. Restored sessions and API
tokens regain their backup-time state: credentials revoked after the snapshot may become valid
again. Review/revoke them after a recovery if needed. Never restore a file from an untrusted source.

## Automated encrypted backups

### Enable, disable, or change the daily time

Automated backups are **disabled by default**, with a suggested time of **02:00 Asia/Kolkata**.
Only superusers may configure them or queue a manual run.

1. Generate a separate Fernet key:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Set `BACKUP_ENCRYPTION_KEY` in the web and worker environment (`.env.dev` or `.env.prod`) and
   restart those processes. Keep an off-host copy of this key separately from the backups.
   Do not reuse `DJANGO_SECRET_KEY` or `SETTINGS_ENCRYPTION_KEY`. Keep old backup keys if rotating.
3. Open **Ops > Backups**, choose the destination, daily time, and IANA time zone, and enable
   backups. Save the settings. All fields and credentials are configured here, not in cron.
4. Keep Celery Beat and a worker running. The saved daily entry uses django-celery-beat. The
   general **Ops > Schedule** page displays it read-only with a link back to **Backups**.
5. Use **Run configured backup now** to test. Check the last run link or **Ops > Runs** for
   success/failure and the storage location. A queued job is not proof of a successful backup.
6. To stop future backups, clear **Enabled** and save. The Beat entry is disabled, and queued
   tasks check the flag before starting. An upload already in progress may finish.

The worker takes a consistent snapshot, releases database locks, encrypts it, and only then
uploads/writes it. SQLite reserves its writer lock before reading; PostgreSQL locks application
tables for the short export transaction. Other writes can briefly wait during export; uploads
do not hold these locks. Restores still require a maintenance window.

The configuration keeps the superuser who last saved it as its owner. Automated jobs fail if
that account is removed, inactive, or no longer a superuser. Save the configuration using another
active superuser to reauthorize it. Upload/write failures are task failures, not success-shaped
fallbacks. Failed S3 uploads do not silently fall back to local disk.

Files have unique timestamped names ending in `.json.enc`. **All files are retained**. Set
lifecycle rules in your S3 provider, or manage folder retention separately. No automated deletion
is performed. Monitor the last successful run and storage capacity externally.

### S3 / S3-compatible storage

Configure an existing private bucket, optional object prefix, region, and access/secret key.
Leave the endpoint empty for Amazon S3. For an external compatible provider, enter its **HTTPS**
endpoint and required region. The bundled MinIO service has one explicit private HTTP exception,
described below. Only a superuser can change these settings. Credentials are encrypted in
the database with the existing settings encryption key; password fields never show saved values.
Leave them blank to keep them, or use **Clear saved S3 credentials** when disabling/changing them.

Give the key only `s3:PutObject` permission for the selected bucket/prefix (and any additional
permission your bucket's mandatory encryption policy requires). This feature does not list or
delete remote objects. HTTPS certificate verification stays enabled.

Network calls run in the worker, not the web server. The supplied production worker already has
the `egress` network. Add your provider to any external firewall allow-list. Rebuild the application
image after deploying the new `boto3` dependency.

### Bundled MinIO service

MinIO is included by default in development and production. Its S3 API is compatible with the
backup uploader; no separate backup implementation is needed. The image is release-pinned.
Review upstream maintenance/security updates when upgrading the deployment.

Before your first `docker compose up`, create your usual application environment file:

```bash
# Development:
cp .env.example .env.dev
chmod 600 .env.dev
# Production instead:
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

If the environment file already exists, edit it instead of replacing it. Set unique
`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` values in `.env.dev` or `.env.prod`. Generate random values
with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Blank values fail startup
instead of using MinIO's built-in default login. Both `minio` and the one-shot `minio-init`
service use the same environment file as the application: `.env.dev` in development and
`.env.prod` in production. These services therefore receive the shared file's other variables too;
keep that file restricted. Caddy and docs still do not receive it.

The initializer waits for MinIO readiness, then creates two **private** buckets:

- `kashengine-backups`: encrypted database snapshots.
- `kashengine-reports`: reserved for future report PDFs.

Initialization is idempotent: existing buckets and objects are not deleted or overwritten.
It does not reset policies on existing buckets; keep them private. **PDF rendering, PDF download
routes, and report uploads are not implemented in this change.** The reserved bucket is storage
preparation only. Future PDF access should go through authenticated application routes, not a
public bucket. Use a separate report credential/policy rather than the backup upload credential.

In development, the S3 API is at `http://127.0.0.1:9000` and the console is at
`http://127.0.0.1:9001`, bound to loopback only. Sign into the console with the admin credentials
to provision a dedicated backup access key. In production neither port is published; the service
is only on the internal `backend` network, with no internet route. Do not open the console to the
internet. For production administration, run the bundled `mc` inside the MinIO container (its root
credentials are already available there), or use a temporary loopback-only Compose port override
and an SSH tunnel.

For example, initialize an admin client in the container:

```bash
docker compose exec minio sh -ec '
  mc --config-dir /tmp/minio-admin alias set storage http://127.0.0.1:9000 \
    "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
  mc --config-dir /tmp/minio-admin admin info storage
'
```

Include your usual `--env-file` and Compose file flags for production commands. Use
`mc admin user`, `mc admin policy`, and/or `mc admin accesskey` to create a separate identity
restricted to `s3:PutObject` on `arn:aws:s3:::kashengine-backups/kashengine/*`, matching the prefix
you choose. Do not grant read/list/delete access to the backup writer or use the root login in
the application. Give restore operators separate read access.

In **Ops > Backups**, set:

| Field | Value |
| --- | --- |
| Destination | S3 / S3-compatible bucket |
| Endpoint | `http://minio:9000` |
| Bucket | `kashengine-backups` |
| Prefix | `kashengine` |
| Region | `us-east-1` |
| Access / secret key | Dedicated MinIO upload credential |

The worker resolves the Docker service name `minio`. Do not put `localhost` in its endpoint:
that points to the worker itself. Only the exact endpoint `http://minio:9000` is allowed over
HTTP; all external endpoints still require HTTPS. S3-compatible endpoints use path-style bucket
addressing. The backup is encrypted **before** it crosses this private HTTP connection; S3
credentials and metadata still rely on Docker network isolation. Use external HTTPS storage if
the host/network is not trusted.

Set `BACKUP_ENCRYPTION_KEY`, enable the daily schedule, and run a test backup as described above.
The MinIO service being enabled does not automatically enable database backups or choose it as
the destination.

Objects persist in the named volume `minio_data`. Do not run `docker compose down -v` if you want
to retain them. A single-node MinIO instance on the application host is **not off-host disaster
recovery**: replicate/copy backups to another machine or provider, or select external S3 for the
automated backup destination. Protect the volume separately. Database snapshots do not include
MinIO objects, including future PDF reports. A future report archive needs object backup and
database/object consistency procedures in addition to database recovery.

### Local / mounted drive folder

Enter an **absolute directory path as seen by the worker**, not a browser download path. The
directory must already exist and be writable by the application UID/GID. The worker writes a
private temporary file with mode `0600`, flushes it, and renames it into place only after writing
all encrypted bytes. This also works with a host-mounted external drive or network share.

Production containers have a read-only root filesystem. Add a writable bind mount or volume for
the worker in a private Compose override, for example:

```yaml
services:
  worker:
    volumes:
      - /srv/kashengine-backups:/backups
```

Create the host directory with restrictive permissions and ownership matching the application's
UID/GID, include the override in your normal Compose invocation, and set the backup folder to
`/backups` in Ops. Keep the existing log volume when merging your override. Do not store backups
only inside a disposable container filesystem. A folder on the same host is not off-host disaster
recovery; copy it to protected independent storage.

### Restore an automated backup

Download the `.json.enc` object from S3 or copy it from the mounted folder using your storage tools.
On the restore target, set the original `BACKUP_ENCRYPTION_KEY`, apply the same migrations, and
import the file through Ops or `database_snapshot import`. Authentication/decryption is verified
**before** any database records are replaced. A missing/wrong key or damaged ciphertext leaves
the database unchanged. Encryption keys and files outside the database are never bundled.

## Make a PostgreSQL backup

The command writes a custom-format dump. The file has restrictive permissions.

```bash
umask 077
mkdir -p backups
backup_file="backups/kashengine-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$backup_file"

pg_restore --list "$backup_file" > /dev/null && echo "dump is readable"
```

Do not commit the file. Move it to the backup target over an encrypted channel. Compare the size
or the checksum after the move.

## Test a restore

Do the first restore on a separate machine or in a separate Compose project. A restore replaces
data. Do not run it on production without a maintenance window and an approval.

1. Start only the database: `docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d db`.
2. Load the dump into an empty database:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' \
     < "$backup_file"
   ```

3. Start the other services. Use the same source revision as the backup, or a later one.
   `web` runs `migrate` when it starts.
4. Check these things: you can log in, **Ops > Schedule** shows the schedule, **Ops > Settings**
   shows the secrets as set, the last reports are there, and a manual job runs on **Ops > Jobs**.
5. Write down how long the restore took and each manual step.

To restore into a database that already has tables, stop `web`, `worker` and `beat` first. Then
drop and make the database again, or use `pg_restore --clean --if-exists`. Check the target
before you run the command.

## Recovery notes

- If you lose `SETTINGS_ENCRYPTION_KEY` (or `DJANGO_SECRET_KEY` when the first is empty), the
  saved secrets cannot be read. They show as "not set". Enter them again on **Ops > Settings**.
  The rest of the data is not affected.
- If you change `DJANGO_SECRET_KEY` and `SETTINGS_ENCRYPTION_KEY` is empty, the same happens.
  Also, all web sessions end. API tokens stay valid, because the database holds only their hash.
- Restore the database and the code of the same period. A newer database with older code can fail.
- A download of a model is not a backup. Write down the model name that `LLM_MODEL` uses.
- Without `caddy_data`, Caddy asks Let's Encrypt for a new certificate. Let's Encrypt limits how
  many it gives for one domain each week.

## Decisions for the owner

Choose these before you go live: the backup target, how long to keep backups, the longest data
loss that you accept (RPO), the longest outage that you accept (RTO), the encryption method and
the person who owns the process. Automate the backup only after one restore test works. Watch the
age of the last backup and send an alert when it is too old.
