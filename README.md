# Kash Engine

A bot that sends a daily report on Indian financial news. It reads news from the previous day, scores the sentiment, and predicts how the market will move on the next day. It also lists IPOs to watch.

> Not financial advice. Predictions can be wrong.

## Status

Early development. Phase 1 (project setup) is done. The features below are planned.

- Collect news from free RSS feeds and web pages
- Save company data from Screener.in and update it on a schedule
- Score news sentiment with a local open model (Ollama)
- Predict the next-day market direction
- Score and list upcoming IPOs
- Send the daily report with Telegram (email later)
- Show all data in a web UI (Django, Datastar, Tailwind)

## Stack

- Python 3.13, Django, Celery, Redis
- PostgreSQL
- Ollama (local LLM)
- Docker and Docker Compose
- uv (packages) and ruff (lint and format)

## Project layout

```text
apps/       Django apps: news, companies, ipos, reports, delivery, markets, web, ops
config/     Django project, settings (base, dev, prod), Celery
deploy/     Caddy config for production
```

## Run in development

You need Docker and Docker Compose.

1. Make the env file:

   ```bash
   cp .env.example .env.dev
   ```

2. Start all services:

   ```bash
   docker compose up --build
   ```

3. Open <https://localhost/>. Caddy runs in dev too, with the same Caddyfile as in prod. It makes a local certificate, so the browser shows a warning the first time. See "Trust the local certificate" below. The admin site is at <https://localhost/admin/>.
4. Make an admin user:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

5. Download the dev model:

   ```bash
   docker compose exec ollama ollama pull llama3.2:3b
   ```

In dev, every port is bound to `127.0.0.1`, so only your computer can reach the services:

| Address | Service |
| --- | --- |
| <https://localhost/> | The site, through Caddy (ports 80 and 443) |
| `localhost:8000` | Django directly. It skips Caddy, so use it only to debug |
| `localhost:5432` | PostgreSQL |
| `localhost:11434` | Ollama |

If ports 80 or 443 are in use on your computer, change the `ports` of `caddy` in `docker-compose.override.yml`. Then use that port in the address, for example `https://localhost:8443/`.

In dev, the Content-Security-Policy is report only. The browser console shows a message for each violation, and nothing is blocked.

### Trust the local certificate

Caddy signs the dev certificate with its own local CA. To remove the browser warning, copy the CA certificate from the container and add it to your system or browser trust store:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-local-root.crt
```

Do not commit this file, and delete it when you remove the dev stack.

Dev has hot-reload. The web server, the Celery worker, and Celery beat restart when you change a `.py` file. Rebuild with `docker compose up --build` only when `pyproject.toml` or `uv.lock` changes.

## Run in production

Caddy is the only service that is open to the internet. It gets the TLS certificate and sends the requests to the Django app. No other service has a public port.

You need a server with Docker, a domain name, and 16 GB RAM or more (for the prod model).

1. Point the DNS record of your domain to the server. Open ports 80 and 443 (TCP) and 443 (UDP) on the firewall.

2. Make the env file and put real values in it. Set `SITE_ADDRESS`, `ACME_EMAIL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and all the `change-me` values:

   ```bash
   cp .env.prod.example .env.prod
   chmod 600 .env.prod
   ```

3. Start. The `--env-file` option is needed: Compose reads `SITE_ADDRESS` and `ACME_EMAIL` from it for Caddy.

   ```bash
   docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

4. Make the login and download the model:

   ```bash
   docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser
   docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml exec ollama ollama pull llama3.1:8b
   ```

To test the prod stack on your own computer, set `SITE_ADDRESS=localhost`. Caddy then makes a local certificate, and your browser shows a warning for it.

### Security model

| Part | What it does |
| --- | --- |
| Ports | Only Caddy publishes ports (80, 443) in prod. In dev, all ports are bound to `127.0.0.1`. |
| Networks | `edge`: Caddy. `proxy`: Caddy and web. `backend`: web, worker, beat, db, redis, ollama. The `proxy` and `backend` networks have no route to the internet. `egress`: worker, beat, and ollama only, for outbound requests. |
| TLS | Caddy gets and renews a Let's Encrypt certificate. HTTP goes to HTTPS. Django also sends HSTS and sets secure cookies. |
| Headers | Caddy adds a Content-Security-Policy, a Permissions-Policy, and Cross-Origin-Resource-Policy. It removes the `Server` header. Django adds the other security headers. |
| Limits | Caddy closes slow clients, limits the request body to 2 MB, and has no admin API. |
| Containers | Every container drops all Linux capabilities and cannot gain new ones. Web, worker, beat, and Caddy have a read-only root file system. Logs are rotated. |
| Secrets | Caddy gets only its four values. It does not get the database password or the Telegram token. |
| Admin pages | Set `ADMIN_ALLOWED_IPS` to limit `/admin/` and `/ops/` to your IP addresses or VPN range. |

Notes:

- Docker changes the firewall rules itself. A tool such as `ufw` does not block a port that Docker publishes. This is why no other service publishes a port.
- `ADMIN_ALLOWED_IPS` uses the client address that Caddy sees. With Docker and IPv6, Caddy can see the address of the Docker gateway. Test it from an allowed and from a blocked address.
- The Content-Security-Policy allows the Datastar script from `cdn.jsdelivr.net`. If you serve Datastar from another host, change `script-src` in `deploy/caddy/Caddyfile`. To test a policy change, set `CSP_HEADER=Content-Security-Policy-Report-Only` in `.env.prod` and read the browser console.
- Keep the `caddy_data` volume. It holds the certificate keys. Let's Encrypt limits how many new certificates you can get for a domain each week.
- There is no limit on login attempts yet. Use a long password for the login. A limit (for example `django-axes`) is a good next step.
- Run `python manage.py check --deploy` with the prod settings after each change to the settings. It must show no issues.

## Ops pages

The Ops pages are for admins. They are at `/ops/`. A user with the "staff" flag can look at everything. Only a superuser can change something (start a job, end a session, turn a user on or off). Other users get a 403 page. The menu link "Ops" shows for staff users only.

| Page | What it shows |
| --- | --- |
| Overview | Health checks for the services (database, Redis, Celery workers, beat, LLM server, Telegram), the host (disk, memory, migrations), and the data (news, scoring backlog, quotes, prediction, report, task failures). It refreshes every 15 seconds. |
| Jobs | Every job, with its schedule, its next run, its last run, and the numbers of the last 7 days. A superuser can start a job with "Run now". |
| Runs | The history of all runs (automatic and manual) with the status, the time, the worker, the result, the error, and the text that a command printed. |
| Logs | The end of the log file, newest first. Filter by level, logger, and text. Tokens and passwords are hidden. |
| Metrics | Charts for the last 14 days, the size of the tables and the database, host and Redis numbers, workers, the scoring queue, and the prediction accuracy. |
| Users | All users with their last login, login count, failed logins, active sessions, subscription, and removed features. A superuser can end sessions, turn users off or on, remove features, and give or end a subscription. |
| Subscriptions | Every user with the state of the trial or subscription (trial, active, ended, none, staff). Filter by state. |
| Logins | Logins, logouts, and failed logins with the address and the browser. It marks addresses with many failed logins. |
| Audit | What admins did on the Ops pages. |
| Settings | Change the settings by group (Telegram, report, LLM, news, sentiment, markets, IPOs, companies, login security, web). Superuser only. See "Settings on the dashboard". |
| Schedule | Change when each job runs by itself. Add, change, turn off, delete, or reset entries. |
| Feeds | The news feeds, with the result of the last fetch. Add, turn off, or delete a feed. |
| Instruments | The market symbols and the weights of the global cues in the prediction. |
| Config | The values that the server uses now (a value saved on the dashboard wins). Secrets show only "set (hidden)". |

How it works:

- A Celery signal saves every task run in the database. A manual job makes its row first (status "Waiting"), then the worker updates it.
- An admin cannot type a command. A job is a Celery task or a management command with fixed arguments (see `apps/ops/jobs.py`). A command runs in a worker. A job that waits or runs cannot start again. A job that needs a confirmation (it sends a message or replaces data) shows a check box.
- The task `ops.prune` runs every day at 03:40 IST (the default time; change it on Ops > Schedule). It deletes task runs and login events older than `OPS_RETENTION_DAYS` (default 90), audit events older than a year, and expired sessions. It marks runs that were lost (a worker stopped) as failed.
- The log file is `logs/app.log`. In dev, the server writes it when you run it outside the tests. In prod, web, worker, and beat share it in the `logs` volume. Set `DJANGO_LOG_TO_FILE=false` to turn it off in dev.
- The `httpx` logger is now at WARNING level. At INFO level it wrote the full Telegram URL, which contains the bot token.
- The IP address of a login comes from `X-Forwarded-For`. Caddy sets this header, and the web container has no other way in.
- `ADMIN_ALLOWED_IPS` limits `/ops/` in the same way as `/admin/`.

## Features and subscriptions

Each part of the web app is a **feature**: Daily reports, News, IPOs, Markets and outlook, Companies, and Delivery. The list is in `apps/access/features.py`.

- **Default:** every user has all features.
- **Remove a feature:** an admin unticks it for one user on Ops > Users > (the user). The menu item, the page, and the matching part of the Today page disappear for that user. A removed feature gives a "Not on your account" page (403). The change works at once.
- **Subscription:** a new user gets a trial (default 7 days). An admin can give a paid period, a gift, or a new trial (days to add, or an end date), and can end it at once. Days are added to the current end, or to today if it ended. Each change goes in the history of the user and in the audit trail.
- **The lock rule:** the setting "Require a subscription" (Ops > Settings > Subscription) is **off by default**. While it is off, nobody is locked out, and the trial is only recorded. When it is on, a user with no active trial or subscription sees only the Account page and can log out. Staff and superusers are never blocked.
- **Existing users:** the migration gives each user from before this feature a gift that does not end, so turning the rule on does not lock them out. An admin can end or change it per user.
- **Settings:** the trial days, the length of one paid period, the price, the currency, the notice days, and the text for a locked user are all on Ops > Settings > Subscription. The price is shown on the Account page only. **There is no payment step yet.** An admin gives the subscription by hand.
- **Account page:** `/account/` shows the subscription, the end date, and which features the user has. Every user can open it, also after the subscription ended. A notice shows in every page when the end is near.
- **Safe by design:** the check is in a middleware that looks at the URL name. A test fails if a new web page has no rule (`apps/access/tests/test_coverage.py`). A page that is not a feature must go on the open list on purpose.
- **Order of the rules:** staff pass. Then the subscription rule. Then the removed features.

## Settings on the dashboard

An admin changes the product behaviour on the dashboard. Nothing needs a restart or a new deploy.

- **Order of values:** a value saved on the dashboard, then the environment variable, then the default in `config/settings/base.py`. The `.env` files give only the first values (a fallback). Each settings page shows the default and whether a value is saved. The box "Use the default" deletes the saved value.
- **What is on the dashboard:** the Telegram bot token, the chat IDs and the API address; the report size; the LLM server, model, and timeouts; the news, sentiment, market, IPO, and company options; the market close time; the health-check limits; the login lockout limits; and the web page size. Also the schedule of the jobs, the news feeds, and the market instruments (symbols, weights, scales).
- **The first start:** the database migrations save the default schedule, the 9 news feeds, and the 9 market instruments. After that, the dashboard owns them. "Reset to default" on Ops > Schedule puts the default schedule back.
- **Speed:** each process keeps the values for 5 seconds. A change shows in all web, worker, and beat processes in a few seconds. The beat process uses the database scheduler (`django-celery-beat`) and sees schedule changes by itself.
- **Secrets:** the Telegram bot token is saved encrypted (Fernet). The key comes from `SETTINGS_ENCRYPTION_KEY`, or from `DJANGO_SECRET_KEY` if you leave it empty. A saved secret is never shown again, never written to the audit trail, and never logged. The page shows only "Set" or "Not set". An empty field keeps the saved token. **If the key changes, the saved token cannot be read and shows as "Not set". Enter it again.** Set `SETTINGS_ENCRYPTION_KEY` to a separate value if you plan to rotate `DJANGO_SECRET_KEY`.
- **Who can change it:** superusers only. Staff users can look. Each change goes in the audit trail (old value and new value, except for secrets).
- **What stays in the environment:** the secret key, the database and Redis addresses, the host names, the security flags, and the log setting. A wrong value here can lock everyone out, so a page cannot change them.
- **If the database cannot be read,** the server uses the environment values, so the pages and the health checks still work.

### Login lockout (django-axes)

After `LOGIN_FAILURE_LIMIT` failed logins (default 5) from one IP address, that address is locked for `LOGIN_COOLOFF_MINUTES` (default 30). With 0 minutes, it stays locked until a superuser unlocks it on Ops > Logins. A correct password does not work during a lockout. A good login resets the count. The address is the first value of `X-Forwarded-For` (Caddy sets it) or the connection address. Both limits are on Ops > Settings > Login security.

### What normal users see

Normal users never see a message about the config or the infrastructure (for example "No Telegram chat is set"). They see a short neutral text (for example, that there is no data yet). Staff users see the real hint and a link to the page where they fix it.

## Settings files

| File | Use |
| --- | --- |
| `.env.example` | Template for dev. Copy to `.env.dev` |
| `.env.prod.example` | Template for prod. Copy to `.env.prod` |
| `.env.dev`, `.env.prod` | Real values. Not in Git |

The settings module is `config.settings.dev` or `config.settings.prod`. The variables `NEWS_FETCH_EVERY_HOURS`, `REPORT_HOUR`, and `REPORT_MINUTE` are gone. Use Ops > Schedule.

## Development tools

```bash
uv sync                         # install packages
uv add <package>                # add a package
uv add --group dev <package>    # add a dev package
uv run ruff check --fix .       # lint (rules: see [tool.ruff] in pyproject.toml)
uv run ruff format .            # format
uv run ty check                 # type check
uv run pytest                   # test (a warning fails the run)
uv run pre-commit install       # turn on commit hooks (ruff, ruff format, ty)
```

Code standards:

- Docstrings use the Google style. Every public module, class, function, and method in `apps/`
  (except tests) has one. The first line is a short summary that ends with a period.
- A comment explains why the code does something. It does not repeat what the code does.
- Fix the cause of a ruff or ty message. Use a `# noqa: CODE` or `# ty: ignore[rule]` comment only
  when the code is correct, and always give the reason after it.
- ruff and ty must report no errors. The commit hooks run both.
