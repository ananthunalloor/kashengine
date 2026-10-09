# Kash Engine: Phase 9 plan and deployment checklist

Status: **plan only**. Nothing is deployed. Date of this plan: 7 October 2026.
Base: branch `phase8-sync` (Phases 1 to 8, 455 tests pass, ruff and `ty` clean for the new code).

## 1. Goal of Phase 9

Make Kash Engine safe and quiet to run every day. When Phase 9 is done:

1. A push to GitHub runs the checks by itself (lint, tests, migrations, Docker build).
2. The server has no known security gap that we can close in code.
3. If the daily report does not reach you, you get an alert. You do not find out by silence.
4. The database is backed up, and you have restored one backup to prove it works.
5. We have run the bot in shadow mode for at least 30 trading days. We know if the prediction beats the baseline.
6. There is a README, a runbook, and a tagged release (`v0.1.0`).

## 2. Where we are now (checked in the repo)

| Area | State |
| --- | --- |
| Code | Django 6.1, 8 apps, Celery beat with 12 scheduled tasks, 455 tests |
| Quality | `ruff` clean. `ty` shows 37 old diagnostics (mostly in test files, `scraper.py`, `prod.py`). No CI. No coverage number |
| Security | `check --deploy` gives 1 warning (HSTS preload, we skip it on purpose). Every web page needs a login. Admin is at `/admin/` |
| Docker | Separate dev and prod compose files. Web, db, and redis have health checks. Worker, beat, and ollama have none |
| Backups | None |
| Alerts | None. Errors go to the log file only |
| Sources | IPO fetch, GMP fetch, and Screener are OFF by default. News feeds and Yahoo quotes are ON |
| Model quality | Unknown. The prediction and the IPO verdict rules are first guesses, not fitted to data |
| Untested live | GMP page (tested on a saved copy only), Yahoo listing price, Yahoo index symbols, Datastar filters in a real browser |

### Gaps that we found while we wrote this plan

- **Start order.** In prod, `worker` and `beat` wait only for `db` and `redis`. They do not wait for `web`, and `web` runs the migrations. A task that fires in the first seconds could run before the tables exist. The risk is small, and the fix is cheap.
- **Unpinned images.** `ollama/ollama:latest` and `ghcr.io/astral-sh/uv:latest` change without notice.
- **No log limit** for Docker's own container logs. The app log file rotates (10 MB, 5 files). Docker's log does not.
- **No model pull step.** The Ollama volume starts empty. The first scoring run fails until the model is there.
- **Datastar comes from a CDN** by default. A CDN outage or change breaks the filters (the pages still work).
- **`gmp.html`** (380 KB) is in the repo. The test fixture replaces it.
- **No login rate limit.** Anyone who can reach `/login/` can try passwords without a limit.

## 3. Work packages

Do them in this order. Packages 1 to 3 are code and are quick. Package 4 needs calendar time (30 trading days), so **start it first** in parallel.

### WP1. Quality gate (about 1 day)

- [ ] Add `.github/workflows/ci.yml`. Steps: `uv sync`, `ruff check`, `ruff format --check`, `pytest` with Postgres 17 and Redis as services, `makemigrations --check`, `check --deploy` with prod settings, `docker build`.
- [ ] Fix or silence the 37 `ty` diagnostics. Then make `ty check` a CI step.
- [ ] Add a coverage report (`pytest --cov`). Set a floor that matches today's number. Do not chase 100%.
- [ ] Run the tests on **Postgres**, not only SQLite. We tested on SQLite so far.
- [ ] Remove `gmp.html`. Add a size limit check (`check-added-large-files` is already in pre-commit).
- [ ] Turn on Dependabot (Python, npm, Docker, GitHub Actions) and run `pip-audit` in CI.

**Done when:** a pull request with a broken test or a lint error cannot merge.

### WP2. Security (about 1 day)

- [ ] Limit login tries. Two options: `limit_req` in Nginx (no new package), or `django-axes` (new package, lock-out per user and IP). Recommended: Nginx first.
- [ ] Do not expose `/admin/` to the whole internet: allow your IP only in Nginx, or put the site behind a VPN (for example Tailscale). Since this is a one-user tool, a VPN is the strongest and the simplest option.
- [ ] Serve Datastar from the site (`static/vendor/datastar.js`, set `DATASTAR_SRC`). Keep the file in Git so the version cannot change.
- [ ] Add a Content-Security-Policy header in Nginx. Check what Datastar needs (it may need `unsafe-eval`). Test it in the browser before you turn it on.
- [ ] HSTS: start with a short time (for example 1 hour), then 1 week, then 1 year. A wrong HSTS setting is hard to undo. Today the code sets 1 year and `includeSubdomains` at once. Change it to read `DJANGO_SECURE_HSTS_SECONDS` from the env.
- [ ] Secrets: `.env.prod` has mode `600` and is owned by the deploy user. New values for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Use a **separate Telegram bot** (and token) for prod. Do not reuse the dev token. If a token was ever pasted in a chat or a log, revoke it with BotFather.
- [ ] Check that `redis`, `db`, and `ollama` publish **no** ports in prod (today they do not; keep it so).
- [ ] Run the containers as the non-root `app` user (already true). Add `read_only: true` and `cap_drop: [ALL]` to `web`, `worker`, `beat` if they still work.

**Done when:** `check --deploy` is clean (except the HSTS preload note), login is rate limited, and `/admin/` is not open to the world.

### WP3. Reliability and operations (about 2 days)

- [ ] `depends_on: web: condition: service_healthy` for `worker` and `beat` in the prod file. Or move `migrate` to a one-shot `migrate` service that the others wait for. (Recommended: the one-shot service.)
- [ ] Health checks for the services that have none: worker (`celery -A config inspect ping -d celery@$HOSTNAME`), beat (the schedule file changed in the last N minutes), ollama (`ollama list`).
- [ ] Pin images: `ollama/ollama:<version>`, `ghcr.io/astral-sh/uv:<version>`, `postgres:17.x`, `redis:7.x-alpine`.
- [ ] Docker log limits: `logging: {driver: json-file, options: {max-size: "10m", max-file: "5"}}` for every service.
- [ ] Ollama: add a one-time step `docker compose exec ollama ollama pull $LLM_MODEL` to the runbook. Add a check in the `web` health (or a command) that says if the model is missing.
- [ ] **Dead-man alert.** A new task at `REPORT_HOUR:REPORT_MINUTE + 45 min` (08:15): if there is no report, or no `sent` log for today (on a trading day), send a Telegram message to an admin chat. Use a second chat ID (`TELEGRAM_ADMIN_CHAT_ID`).
- [ ] **Failure alert.** A Celery `task_failure` signal that sends a short Telegram message (task name and error, with the token redacted), at most one per task per hour.
- [ ] **Backup.** A nightly `pg_dump` (custom format) to a folder, 14 days kept, and a copy off the server (rclone to cloud storage, or `scp` to another machine). Add a restore command to the runbook. **Restore one backup into a new empty database** before go-live.
- [ ] Memory limits for `ollama` (`mem_limit`) so one bad request cannot take the whole server down.
- [ ] Gunicorn: add `--access-logfile -` and `--timeout 60`. Keep 3 workers.

**Done when:** you can stop the worker on purpose and an alert reaches your phone; and you have restored a backup.

### WP4. Does the bot work? Shadow mode (30 trading days, start now)

This package decides if the report is worth reading. Code changes are small. The wait is long.

- [ ] Run the full pipeline with **real feeds** in dev or on a cheap server for 30 trading days (about 6 weeks). Send the report only to yourself.
- [ ] Pick the sentiment model with data: run `compare_models` on 100 articles that you label by hand (good, bad, neutral). Choose the smallest model that agrees with you most of the time. Check how long scoring takes: all articles of a day must be scored before 07:00.
- [ ] After 30 results run `prediction_stats`. Write down the numbers. Rule:
  - Accuracy not better than the baseline (guess the most common result every day) → do **not** claim an edge. The report keeps its honest track-record line. Look at the weights only with evidence.
  - Accuracy better than the baseline by at least 5 points over 30 days (a rule of thumb) → keep going and collect more days. 30 days is still a small sample.
- [ ] After 20 listed IPOs run `ipo_stats`. Same rule for the verdicts.
- [ ] Check the live sources one by one and note the result here: Yahoo index symbols (`^NSEI`, `^BSESN`, `^INDIAVIX`, `USDINR=X`, `BZ=F`), Yahoo listing price, GMP page, chittorgarh feed, each RSS feed.
- [ ] Keep a list of source failures per week (from the logs). A source that fails often needs a fix or a replacement.

**Done when:** you have a written result for the prediction and for the IPO verdicts, and you chose the model by data.

### WP5. Sources and legal (about half a day)

I am not a lawyer. This is a list of points to check, not advice.

- [ ] Read the terms of every source that you turn on: chittorgarh, investorgain, Screener.in, Yahoo (through yfinance), and each news site. Note the date you read them. Keep unclear ones OFF.
- [ ] Put a real contact URL in `NEWS_USER_AGENT`.
- [ ] Keep the data for your own use. Do not show scraped data to other people, and do not publish the report.
- [ ] **If you send the report to other people**, check the SEBI rules on investment advice and research analysts first. A daily "the market will go up" message to others can fall under them.
- [ ] Keep the footer on the web pages and add one line to the Telegram report: not investment advice; GMP is unofficial.

### WP6. Documents and release (about 1 day)

- [ ] Update `README.md`: phases 6 to 8, the web pages, the commands (`build_report`, `send_report`, `refresh_ipo_data`, `prediction_stats`, `ipo_stats`), the CSS build.
- [ ] Write `docs/RUNBOOK.md`: daily check, what to do when the report is missing, when a source fails, when Ollama is down, how to restore a backup, how to rotate secrets.
- [ ] Write `CHANGELOG.md`. Tag `v0.1.0` after WP1 to WP3 are done and shadow mode has started. Tag `v0.2.0` after WP4 gives a result.
- [ ] Decide on email delivery (the original plan). It is **not** in Phase 9 unless you want it: it needs a provider, SPF/DKIM, and an unsubscribe rule. Plan it as Phase 10.

### Order and time

| Step | Work | Calendar time |
| --- | --- | --- |
| 1 | WP4 starts (shadow mode on dev or a cheap server) | 6 weeks, in parallel |
| 2 | WP1 quality gate | 1 day |
| 3 | WP3 reliability | 2 days |
| 4 | WP2 security | 1 day |
| 5 | WP5 sources and legal | half a day |
| 6 | WP6 docs, tag `v0.1.0` | 1 day |
| 7 | Dry run on the server (section 5), then go-live decision | 1 day |

## 4. Decisions that we need from you

1. **Where does it run?** A VPS with 16 GB RAM or more, a home server, or your own computer. The 8B model on a CPU is slow (it can take seconds per article). A small GPU, or the 3B model (`llama3.2:3b`), changes the cost a lot. Measure with `llm_check` before you pay for a server.
2. **Who gets the report?** Only you (simple) or other people (see WP5, SEBI).
3. **How do you reach the site?** A public domain with Nginx and HTTPS, or a private VPN only (recommended).
4. **Do you want email in Phase 10?**
5. **Where do backups go?** Another machine, or cloud storage.

## 5. Deployment checklist (not run; use it on the day)

Tick each box on the server. Stop at the first failure.

### A. Before you start

- [ ] WP1, WP2, WP3 are merged and CI is green on `main`.
- [ ] Shadow mode has run at least 10 trading days without a missed report.
- [ ] You have a server with: 16 GB RAM or more (or the 3B model), 40 GB free disk, Docker Engine and Docker Compose v2, a clock set by NTP (`timedatectl` shows "synchronized: yes").
- [ ] You have a domain and a DNS record for it (or a VPN).
- [ ] You have a separate prod Telegram bot token, your chat ID, and an admin chat ID.
- [ ] You know where the backups go and you can write there.

### B. Prepare the server

- [ ] A normal user for deploys (no root login by SSH, keys only, password login off).
- [ ] Firewall: allow 22 (your IP if you can), 80, 443 only. **Nothing else.** Check with `ss -tlnp` and from outside.
- [ ] `git clone` the repo. Check out the tag: `git checkout v0.1.0`.
- [ ] Nginx and a TLS certificate (certbot). Nginx sets `X-Forwarded-Proto`, passes to `127.0.0.1:8000`, rate limits `/login/`, restricts `/admin/`.
- [ ] `cp .env.prod.example .env.prod` and fill it in. Then `chmod 600 .env.prod`.

### C. Check `.env.prod`

- [ ] `DJANGO_SETTINGS_MODULE=config.settings.prod`
- [ ] `DJANGO_SECRET_KEY` is new and long (at least 50 characters).
- [ ] `DJANGO_ALLOWED_HOSTS` has your domain **and** `localhost`.
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain`
- [ ] `DJANGO_SECURE_SSL_REDIRECT=true`
- [ ] `POSTGRES_PASSWORD` is new, and the same password is in `DATABASE_URL`.
- [ ] `LLM_MODEL` is the model that you chose in WP4.
- [ ] `NEWS_USER_AGENT` has your contact URL.
- [ ] The sources that you turned on are the ones you read the terms for: `IPO_FETCH_ENABLED`, `IPO_GMP_ENABLED`, `SCREENER_ENABLED`.
- [ ] `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS`, `TELEGRAM_ADMIN_CHAT_ID` are set.
- [ ] `REPORT_HOUR` and `REPORT_MINUTE` are what you want (IST).

### D. First start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

- [ ] All services are `running`, and the ones with a health check are `healthy`.
- [ ] `docker compose ... logs --tail=100 web worker beat` shows no traceback.
- [ ] Pull the model: `docker compose ... exec ollama ollama pull <LLM_MODEL>`.
- [ ] `docker compose ... exec web python manage.py llm_check` passes.
- [ ] `docker compose ... exec web python manage.py createsuperuser`.
- [ ] `docker compose ... exec web python manage.py check --deploy` shows no new warning.

### E. Verify, one by one

- [ ] `https://your-domain/health/` answers `{"status": "ok"}`. `http://` redirects to `https://`.
- [ ] `/login/` works. A wrong password shows the error. 10 fast wrong tries are blocked.
- [ ] `/admin/` is **not** reachable from outside your allowed IP.
- [ ] Every page opens after login: Today, Reports, News, IPOs, Markets, Companies, Delivery. Anonymous requests go to `/login/`.
- [ ] The filters on News, IPOs, and Companies update the list without a page reload (this is the one thing that we could not test in the build server).
- [ ] `python manage.py fetch_news` saves articles. `score_news` scores some.
- [ ] `python manage.py fetch_quotes` saves quotes for all instruments (no symbol fails in the log).
- [ ] `python manage.py predict_market` makes a prediction.
- [ ] `python manage.py collect_ipos --force` and `refresh_ipo_data --force` run, if you turned those sources on.
- [ ] `python manage.py telegram_check` shows your chat ID. `python manage.py send_report --test` reaches your phone.
- [ ] `python manage.py build_report`, then open the report on the Reports page. It reads well.
- [ ] Stop the worker (`docker compose ... stop worker`). The failure or dead-man alert reaches the admin chat. Start the worker again.
- [ ] Run the backup script by hand. Restore it into a **new empty database**. The row counts match.
- [ ] Reboot the server. All services come back by themselves. The next scheduled task still runs.

### F. Go-live gates (all must be true)

- [ ] Every box in E is ticked.
- [ ] You can name the person (you) who reads the alert, and the alert works.
- [ ] The report has the "not investment advice" line.
- [ ] You know how to roll back (section G).

### G. Roll back

- [ ] Keep the last good tag. To go back: `git checkout <old-tag>` then `docker compose ... up -d --build`.
- [ ] Migrations only go forward. Before a release with a migration, **take a backup first** (`pg_dump`). To undo a migration, restore that backup.
- [ ] To stop the reports at once without a deploy: set `TELEGRAM_CHAT_IDS=` (empty) in `.env.prod`, then `docker compose ... up -d web worker beat`.

### H. First week after go-live

- [ ] Each morning: the report came before 07:45. Look at the Delivery page.
- [ ] Each day: `docker compose ... logs --since 24h worker | grep -i -E "error|failed|warning"`. Note which sources fail.
- [ ] Day 3: disk use (`docker system df`, `df -h`) and memory (`docker stats --no-stream`) are stable.
- [ ] Day 7: a backup from the last night exists, and it is copied off the server.
- [ ] Day 7: check the accuracy numbers (`prediction_stats`). Do not change a weight on less than 30 results.

### I. Every month

- [ ] Update images and packages in a branch. CI is green. Deploy a tag.
- [ ] Restore one backup (a test).
- [ ] Re-read the terms of the sources that you use.
- [ ] Rotate the Telegram token and the Django secret key every 6 months, or after any leak.
