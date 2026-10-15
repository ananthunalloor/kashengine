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
| `caddy_data` | TLS keys and certificates. Optional: Caddy can get new ones. | Volume `caddy_data` |
| `ollama_data` | Downloaded models. Optional: you can download them again. | Volume `ollama_data` |
| Source revision | The code must match the database schema | Git |

Redis has no volume and holds no data that you must keep. It holds the Celery queue and the API
rate-limit counters. After a restart the queue is empty and the counters start again from zero.
The Beat schedule is in the database, so a restore brings it back.

Store the keys apart from the database backup. Never put a plain `.env.prod` in a general backup
archive.

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
