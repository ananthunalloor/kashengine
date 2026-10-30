# Kash Engine

A bot that sends a daily report on Indian financial news. It reads news from the previous day, scores the sentiment, and predicts how the market will move on the next day. It also lists IPOs to watch.

> Not financial advice. Predictions can be wrong.

## Automated forecasts and watchdog

Market direction, mapped-company outlooks and pre-listing IPO scores refresh from saved
provider/news inputs every **15 minutes**. Existing data-collection and news-scoring jobs still
provide those inputs; a forecast never fabricates a missing price. Celery **worker and beat**
must both be running, and Upstox company history still requires its opt-in and a valid token.
Apply migrations and restore dependencies (`uv sync`) before restarting web and workers.

Each forecast family has a trained, regularized logistic-regression challenger. Daily at
**05:00 IST**, the trainer collects completed outcomes and tests a new model chronologically:

- At least **60 training dates**, followed by at least **20 untouched validation dates**.
  Company rows sharing a target date stay together; many stocks on one day do not count as
  many independent validation dates.
- Training outcomes must have been observable before the first validation forecast.
  Late inputs, blocked samples and incompatible outcome definitions are excluded.
- The model must beat **both** the holdout's most-common-result baseline and the existing
  rule by at least **5 percentage points**. Otherwise it is not deployed.
- Until sufficient prospective evidence exists, the explainable rule remains explicitly
  **experimental**. No historical training examples are invented from today's revised data.
  Model strengths are not calibrated probabilities. Models expire after seven days without
  revalidation, and failed validation removes their approval.

An independent deterministic watchdog recalculates rule and classifier outputs before publication, checks
normalized values and deadlines, and audits saved predictions every **15 minutes**, offset
seven minutes from refreshes. Versioned model coefficients are retained for independent replay.
Invalid, missing, stale or late evidence is withheld, not
presented as “flat,” “neutral,” or “likely good.” Reports, UI and accuracy statistics respect
withholding; cached market-report copies are withdrawn if the scheduled audit finds corruption.
The watchdog checks consistency and available evidence, **not the truth of an external feed or
future market movements**. It is not a second LLM asserting that another model is correct.

Forecast evidence refreshes only before the target session opens and freezes at that deadline.
Company outcomes use the next completed close versus the recorded reference close. Market
outcomes use final target-index changes. IPO outcomes use the actual listing price versus the
recorded issue price (good means the configured `IPO_GOOD_GAIN_PCT`). Same-day subscription
figures are not treated as final during the bidding close date.

Use **Ops > Jobs** for **Refresh all forecasts**, **Train and validate forecast models**, and
**Audit predictions**. Read-only Django admin entries for **Forecast models** and
**Forecast samples** expose validation metrics and watchdog reasons. Public API v1 omits
withheld predictions from history and returns 404 for a withheld latest outlook, preserving
its existing direction enum; the browser history explicitly shows **Withheld**.

Unexpected IPO scoring/watchdog errors abort new report generation rather than falling back to
cached, unchecked recommendations.

The first audit also withholds active legacy forecasts without watchdog provenance rather than
retroactively certifying them or inventing training snapshots. New valid pre-session evidence
replaces these on subsequent refreshes.

The company's client-side chart projection remains an illustrative linear extrapolation,
not the trained next-session forecast or a validated price target.

## Status

Early development. Phase 1 (project setup) is done. The features below are planned.

- Collect news from free RSS feeds and web pages
- Save company data from Screener.in and update it on a schedule
- Score news sentiment with a local open model (Ollama)
- Predict the next-day market direction
- Score and list upcoming IPOs
- Send the daily report with Telegram (email later)
- Show all data in a React web application
- Read the data with a versioned, read-only REST API (`/api/v1/`, with Swagger UI)

## Stack

- Python 3.13, Django, Celery, Redis
- PostgreSQL
- Silo (private S3-compatible storage for encrypted backups; PDF report storage planned)
- Ollama (local LLM)
- Docker and Docker Compose
- uv (packages) and ruff (lint and format)

## Live updates and notifications

The top of every signed-in page shows dismissible Mantine alerts for scheduled market
closures, special sessions, subscription warnings, and persistent live-update notices.
Closing a market or subscription alert hides that version while you navigate; changed
status/messages appear again, and the account page still shows subscription details.
The **Trading calendar** button remains available after dismissal. It opens a year-by-year
NSE cash/equity holiday and special-session list, including reasons, session hours in IST,
and exchange circular links.

Staff with Django admin permissions maintain entries at
`/admin/markets/tradingcalendarday/`. Apply migrations before deploying. Each date has one
entry and a required reason; special sessions require same-day opening and closing times.
No official holiday feed or pre-populated dates are supplied: an empty year explicitly warns
that dates have not been entered. Verify announcements using the official NSE link in the
calendar. Unlisted weekdays assume 09:15 IST opening and the configured `MARKET_CLOSE_TIME`;
unlisted weekends are closed. These exceptions also drive prediction/report trading-day
selection and special-session evaluation closing times. Market status refreshes at session
boundaries, midnight, and on calendar edits; it describes the schedule, not live exchange health.

The signed-in React app uses same-origin Server-Sent Events (SSE) to refresh data without
reloading the page. Staff also receive job completion/failure notifications with links to
task details. Actions, API errors, token changes, subscription notices, and connection
failures use Mantine notification cards with the app's light/dark brand colors. Success
messages close after eight seconds (paused while hovered or focused); errors stay until
dismissed. Inline form errors remain available.

- Apply migrations with `python manage.py migrate` before starting the updated web server
  **and** workers. Events are stored in the database, shared across processes, and published
  after transactions commit. `ops.prune` keeps one day of replay history.
- `/api/app/events` exposes only data invalidations. `/api/app/ops/events` additionally
  exposes staff-only task IDs, labels, and statuses, under the existing Ops IP allowlist.
  Secrets, task output, tracebacks, and form values are never sent in events.
- Connections heartbeat every second, reconnect automatically, resume with `Last-Event-ID`,
  and recheck session/staff access at least every 20 seconds. Initial connections do not
  replay historical job popups. Routine stream renewals replay changes without refetching
  unchanged data. A connection failure or expired replay history resynchronizes visible queries.
- Model saves/deletes and relationship edits refresh affected pages. Job completion also
  refreshes all pages to cover bulk writes inside jobs. Code performing bulk writes outside
  a job must call `apps.api.live.publish("all")` after its changes (the helper defers to commit).
  Status and table data refetch only on change events, not periodic SSE ticks. Opted-in logs
  refresh on changes while visible and pause on errors. External runtime diagnostics and log
  changes without a model event require manual Refresh; no API polling is used.
- Production Gunicorn uses threaded workers so streams do not occupy every sync worker.
  Each open tab occupies one thread; size workers/threads and database connections for your
  concurrent users, leaving headroom for normal requests. Proxies must not buffer SSE;
  Django sends `text/event-stream` and `X-Accel-Buffering: no`.

## Project layout

```text
apps/       Django apps: news, companies, ipos, reports, delivery, markets, web, ops
config/     Django project, settings (base, dev, prod), Celery
deploy/     Caddy config for production
```

## Upstox company data, news and IPOs

Upstox is **opt-in** and supplements the existing sources; disabling it does not delete saved
data or disable RSS, Yahoo Finance, or Screener collection. Current official APIs support
[news](https://upstox.com/developer/api-documentation/get-news/),
[IPO lists](https://upstox.com/developer/api-documentation/get-ipos/),
[IPO details](https://upstox.com/developer/api-documentation/get-ipo-details/), and
[company fundamentals](https://upstox.com/developer/api-documentation/fundamentals/).
Check your Upstox/exchange entitlements and data-storage/display terms before enabling or
redistributing data. API availability does not itself grant redistribution rights.

1. Restore dependencies with `uv sync`, then run `python manage.py migrate` before restarting
   web, worker and beat processes. Build the React app with `pnpm --dir frontend build`.
2. In **Ops > Settings > Markets and prediction**, enable Upstox and save its access token.
   Saved tokens use the existing encrypted settings store. Alternatively set `UPSTOX_ENABLED`
   and `UPSTOX_ACCESS_TOKEN` in your private environment. Never put tokens in browser URLs.
   Obtain and renew tokens through Upstox's supported authentication flow; automatic OAuth
   enrollment/token renewal is not implemented. Expired tokens produce explicit refresh failures.
3. The built-in starter company list includes verified Upstox instrument keys. For other companies,
  set the **Upstox instrument key** in Django admin using an exact key from Upstox's instrument
  list, not a guessed symbol. Company prices, fundamentals, and company-linked news require these
  mappings. IPO ingestion does not. Matching ISINs link IPOs to saved companies.
4. Run **Refresh Upstox data** on **Ops > Jobs** for the initial import. It saves one year of
   daily OHLCV history, due fundamentals, all news pages, and IPO details across all four lifecycle
   stages. New news enters the existing LLM scoring queue; IPOs use the existing scoring rules.

The migrations add two editable beat schedules without overwriting existing schedule entries:

- Quote snapshots every **five minutes**, only inside the saved NSE session (including special
  weekend sessions). Each quote records provider time, price, previous close and volume.
- Company/news/IPO refresh every **six hours**. Historical bars refresh incrementally with an
  overlapping last day for corrections. Fundamentals refresh at most once per seven days
  (`UPSTOX_FUNDAMENTALS_DAYS`), with older successful snapshots retained. They include profile,
  key ratios, consolidated balance sheet, cash flow, annual income statement, shareholding and
  corporate actions. Monetary units and reporting periods remain attached to provider data.

### Live market data (WebSockets)

The **Today** dashboard and company pages show live Upstox prices when the Markets feature is on:

- **Today**: a *Live market* strip with index levels (Nifty 50, Sensex, Nifty Bank and India VIX
  by default), the change from the previous close, the day range and the exchange session state.
  Stocks in *Stocks to watch today* show their live price and change.
- **Company page**: a live price in the header and a live quote panel with last price, change,
  open/high/low/previous close, volume, average traded price, total buy/sell quantity, a buy/sell
  pressure bar and the top 5 levels of market depth. The *Trading session* card uses live values.
  Without live ticks, the page falls back to the saved quote.

How it works:

```
Upstox V3 market feed --(wss, protobuf, full mode)--> streamer (stream_upstox)
    --> LiveSnapshot (newest value per instrument) + CompanyQuote (at most one per 5 s)
    --> Redis channel layer --> realtime (Django Channels on Uvicorn) --(wss /ws/live/quotes/)--> browser
```

- Compose runs two extra services in dev and prod. **`streamer`** keeps a single connection to
  Upstox and **`realtime`** relays the quotes to browsers. Caddy sends only `/ws/*` to
  `realtime`. Every other request, including the SSE event stream, stays on the WSGI `web`
  service. The browser never connects to Upstox and never sees the token.
- The socket accepts only same-origin, signed-in, email-verified accounts with an active
  subscription and Markets access. It re-checks the session every minute. A browser follows all
  streamed indices plus up to 25 companies.
- Quotes are batched and broadcast about once a second. Stream writes do not fire model
  signals, so they do not trigger SSE refetch storms.
- The worker reconnects forever with backoff of up to 60 s. While Upstox is off or has no token,
  it waits and retries, so a token saved in Ops is used without a restart. Company mappings and
  stream indices are read again on each reconnect.
- Docker runs the feed command directly and restarts it if it exits, including startup-check
  failures. The streamer does not use a file-watcher: after editing its Python code in dev,
  run `docker compose restart streamer`. A container restart does not fix a persistent
  configuration error; check `docker compose logs streamer` if quotes stay old.
- Set the indices with `UPSTOX_STREAM_INDICES` (**Ops > Settings > Markets and prediction**,
  or the environment). Full mode allows 2000 instruments per connection, and indices count
  towards this limit. Run **only one** streamer per Upstox token.
- Ticks older than a minute are shown as *delayed*, not live.

To run the worker outside Compose:

```bash
uv run python manage.py stream_upstox
# Or subscribe to a subset, or without indices:
uv run python manage.py stream_upstox --symbols RELIANCE INFY --no-indices
# Run the browser socket server:
uv run uvicorn config.asgi:application --port 8001
```

REST snapshots continue as a fallback. A late REST observation cannot hide a newer stream quote.
Streaming observations, daily bars, and fundamentals snapshots are retained, so plan database
capacity and backups for the number of companies you track.

### Pages and saved scores

- `/markets/live/`: paginated market observations for the saved company directory, searchable
  by name or symbol, with provider timestamps, observation type, missing quotes and refresh errors.
- `/companies/`: directory links now open `/companies/<id>/`, with summary, saved fundamentals,
  OHLCV history and trend chart, linked news sentiment/relevance, IPO scores, and scoring evidence.
- IPO detail pages also show the saved Upstox timeline, registrar and complete provider facts.

These pages and their private APIs **only read the database**. They never call providers or
recompute scores on a page request. Existing SSE invalidations update visible data when a worker
saves changes; freshness labels age locally without API polling. Live prices come over the
`/ws/live/quotes/` WebSocket described above. Old observations are explicitly not labelled
live, including when the stream disconnects or the market is closed.
Each dataset continues to respect the account's Companies, Markets, News and IPO feature access.

The company future-trend outlook is **experimental, unbacktested, and not financial advice**.
It requires 21 recent completed daily bars. Momentum is the 20-session return divided by 10%,
clipped to [-1, 1]. With scored company news from the previous seven days, the combined signal
is 70% momentum and 30% relevance-weighted sentiment; without news it uses momentum alone.
Scores above +0.15 point up, below -0.15 point down, and otherwise flat. Evidence, target session,
creation time and all inputs are saved. This is neither a price target nor a probability.
Unadjusted prices mean corporate actions can distort momentum. Historical outlooks retain their
original target dates and are not presented as current forecasts.

## Run in development

You need Docker and Docker Compose.

1. Make the env file:

   ```bash
   cp .env.example .env.dev
   chmod 600 .env.dev
   ```

   Set unique `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` values in `.env.dev` before starting.
   Silo retains these variable names for compatibility and uses the same environment file as the app.

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
| `localhost:9000` | Silo S3 API |
| <http://localhost:9001/> | Silo console (root/admin login; development only) |

Silo starts automatically and initializes private `kashengine-backups` and `kashengine-reports`
buckets without deleting existing objects. Use **Ops > Backups** to select S3 storage and endpoint
`http://silo:9000` from the worker container. Use a dedicated upload-only credential.
The reports bucket is reserved for future PDF storage; PDF generation is not implemented.
See [Silo backup setup](docs/docs/operations/backups-and-recovery.md#bundled-silo-service).

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

2. Make the env file and put real values in it. Set `SITE_ADDRESS`, `ACME_EMAIL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, and all the `change-me` values. Point the domain at the server and include it in the allowed hosts and trusted origins:

   ```bash
   cp .env.prod.example .env.prod
   chmod 600 .env.prod
   ```

   Set unique Silo root credentials in `.env.prod` using the `MINIO_ROOT_*` variable names.
   Production does not publish the Silo API or console ports. Its data persists in the existing
   `minio_data` volume; keep an independent off-host copy.

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
| Networks | `edge`: Caddy. `proxy`: Caddy and web. `backend`: web, worker, beat, db, redis, ollama, silo, silo-init. The `proxy` and `backend` networks have no route to the internet. `egress`: worker, beat, and ollama only, for outbound requests. |
| TLS | Caddy gets and renews a Let's Encrypt certificate. HTTP goes to HTTPS. Django also sends HSTS and sets secure cookies. |
| Headers | Caddy adds a Content-Security-Policy, a Permissions-Policy, and Cross-Origin-Resource-Policy. It removes the `Server` header. Django adds the other security headers. |
| Limits | Caddy closes slow clients, limits the request body to 2 MB, and has no admin API. |
| Containers | Every container drops all Linux capabilities and cannot gain new ones. Web, worker, beat, and Caddy have a read-only root file system. Logs are rotated. |
| Secrets | Caddy gets only its four values. It does not get the database password or the Telegram token. |
| Admin pages | Set `ADMIN_ALLOWED_IPS` to limit `/admin/`, `/ops/`, `/ops/`, and `/api/app/ops/` to your IP addresses or VPN range. |

Notes:

- Docker changes the firewall rules itself. A tool such as `ufw` does not block a port that Docker publishes. This is why no other service publishes a port.
- `ADMIN_ALLOWED_IPS` uses the client address that Caddy sees. With Docker and IPv6, Caddy can see the address of the Docker gateway. Test it from an allowed and from a blocked address.
- The Content-Security-Policy allows the Datastar script from `cdn.jsdelivr.net`. If you serve Datastar from another host, change `script-src` in `deploy/caddy/Caddyfile`. To test a policy change, set `CSP_HEADER=Content-Security-Policy-Report-Only` in `.env.prod` and read the browser console.
- Keep the `caddy_data` volume. It holds the certificate keys. Let's Encrypt limits how many new certificates you can get for a domain each week.
- There is no limit on login attempts yet. Use a long password for the login. A limit (for example `django-axes`) is a good next step.
- Run `python manage.py check --deploy` with the prod settings after each change to the settings. It must show no issues.

## Web entry points

The public landing page at `/` introduces the app with capability cards, expandable details,
an illustrative daily brief, and links to sign in. It does not display live account or market data.
Signed-in users open the protected Today dashboard at `/dashboard/`; report, news, IPO, and other
application pages still require login and their existing access permissions.

### Score display

The web UI and newly built Telegram reports show scores with one decimal place out of 10:

- Sentiment, market component scores, and IPO scores/signals map `-1..1` to `1.0..10.0`
  (`1 + 4.5 × (score + 1)`). Neutral is `5.5/10`; higher means more positive.
- Signal strength and news relevance map `0..1` to `1.0..10.0` (`1 + 9 × value`).
  Strength is not a probability of being right.
- Accuracy, price changes, GMP percentages, subscription multiples, and prices keep their units.

This is presentation only: stored numeric scores, API values, scoring rules, filter thresholds,
and verdicts do not change. No database migration is needed. Archived reports with saved
structured data are reformatted when viewed, without overwriting their saved text or data.
Legacy reports without structured data retain their original body text. Future report builds
use the new display format; already-sent Telegram messages are not edited.

## Ops pages

The Ops pages are for admins. The complete React workspace is at `/ops/`; the original
`/ops/` pages and URLs remain available. Staff can inspect operations; database backups require
a superuser even for viewing. Only superusers can make changes (start jobs, manage users,
settings, schedules, feeds, instruments, and backups). Other users get a 403 response.
The workspace's Ops link and sub-navigation show only to staff.

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
| Backups | Superuser-only encrypted backup configuration, run-now, snapshot download, and replacement restore. Existing maintenance warnings, size limits, RESTORE confirmation, and sign-out are retained. |

How it works:

- A Celery signal saves every task run in the database. A manual job makes its row first (status "Waiting"), then the worker updates it.
- An admin cannot type a command. A job is a Celery task or a management command with fixed arguments (see `apps/ops/jobs.py`). A command runs in a worker. A job that waits or runs cannot start again. A job that needs a confirmation (it sends a message or replaces data) shows a check box.
- The task `ops.prune` runs every day at 03:40 IST (the default time; change it on Ops > Schedule). It deletes task runs and login events older than `OPS_RETENTION_DAYS` (default 90), audit events older than a year, and expired sessions. It marks runs that were lost (a worker stopped) as failed.
- The log file is `logs/app.log`. In dev, the server writes it when you run it outside the tests. In prod, web, worker, and beat share it in the `logs` volume. Set `DJANGO_LOG_TO_FILE=false` to turn it off in dev.
- The `httpx` logger is now at WARNING level. At INFO level it wrote the full Telegram URL, which contains the bot token.
- The IP address of a login comes from `X-Forwarded-For`. Caddy sets this header, and the web container has no other way in.
- `ADMIN_ALLOWED_IPS` limits `/ops/`, `/ops/`, and `/api/app/ops/` in the same way as `/admin/`.

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

React is the main UI at the original URLs: `/`, `/login/`, `/dashboard/`, `/news/`, and
the other subscriber and `/ops/` pages. The former `/app/` prefix has been removed.
The landing page preserves the
capabilities, illustrative market brief, workflow, research limitations, and shared purple
light/dark theme. Login uses native POSTs to Django's existing authentication and django-axes;
passwords are never serialized into presentation data or client caches. Real feature/permission
denials and login lockouts render React with their original 403/429 statuses.
Authentication, logout, and subscription redirects stay within React. Django Admin,
API documentation, and the documentation site are intentionally outside this migration.

Undefined browser URLs display a themed React 404 with home/dashboard recovery links and
retain HTTP 404 (also for anonymous visitors). React navigation has the same catch-all
screen. Existing API error handling and protected-route permissions remain unchanged.

The React application is developed in `frontend/`. Install the pinned pnpm release with
Corepack, then run the Django server and Vite server together:

```bash
corepack enable
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

Open `http://localhost:8000/` for the landing page, then sign in to the React dashboard.
The application loads navigation, feature permissions, subscription notices, and the staff flag
from the session-only private API at `/api/app/session`. Reports, News, IPOs, Markets, Companies, and Delivery open React pages at
`/reports/`, `/news/`, `/ipos/`, `/markets/`, `/companies/`, and `/delivery/`. The shell includes a mobile menu,
a persistent light/dark toggle, and CSRF-protected logout.
An expired session returns to login; API errors display a retryable error page.

The Reports page includes paginated history, full text, delivery status, and adjacent-report
navigation, using `/api/app/reports` and `/api/app/reports/{day}`. Reports access rules are preserved; delivery
recipients are never exposed and delivery errors are staff-only.

The News page preserves headline/summary search, source and sentiment filters, pagination,
model explanations, company names, and the existing 1.0-10.0 score scale. Filters live in the URL
for bookmarks and back/forward navigation. Search updates after a short debounce; Apply and Clear
filters are also available. `/api/app/news` and `/news/` enforce the same feature and subscription rules.

The IPO page includes Active and listed history, search, board/verdict/status filters,
pagination, and issue detail pages at `/ipos/{id}/`. Facts retain the original units and
freshness notices; verdict evidence uses saved scores rather than recalculating them.
The session-only `/api/app/ipos` and `/api/app/ipos/{id}` endpoints enforce the IPO feature and
subscription rules.

The Markets page at `/markets/` shows the existing accuracy/baseline statistics, latest
saved instrument closes with their trading dates, and the newest 30 predictions. Right, Wrong,
Waiting, and No session remain distinct; strength is not a probability. Its session-only
`/api/app/markets` endpoint reuses the existing queries and evaluation statistics without
downloading prices or evaluating predictions.

The Companies page at `/companies/` preserves name/symbol/sector search, alphabetical
ordering, pagination, source links, and last-fetched dates in IST. Search is debounced and stored
in the URL for bookmarks and browser history. The session-only `/api/app/companies` endpoint
uses the existing company query and enforces company feature/subscription rules; scraped data
and aliases are not exposed.

The Delivery page at `/delivery/` shows the newest 50 send attempts, configuration chat
count, channels, results, and IST timestamps. Report links stay inside React and are shown only
when Reports is available. The session-only `/api/app/delivery` endpoint enforces Delivery access,
excludes recipient identifiers and bot credentials, and returns diagnostics only to staff.
Reading the page never sends messages.

React shares the landing page's purple accent, white surfaces, sans-serif typography, and rounded
cards through `static/css/brand-tokens.css`. Light mode is the default; a saved dark-mode choice
is retained. Theme changes use static CSS and do not weaken the Content-Security-Policy.

The React workspace uses React Icons (Lucide set) for navigation and controls, with a shared
TanStack Table for Today summaries, Reports, News, IPOs, Companies, Markets, Delivery, and detail-page tables.
Sortable headers, accessible search/filters, row-size selection, and first/previous/next/last
pagination share one responsive design. Signed-in pages use the full content width beside the
navigation, without a page-width cap and with a small responsive side gutter. Ops tables also extend through
their section's side padding. Tables that still exceed the available width scroll within their
panel, not the page.
Ops row Actions headers and cells stay pinned to the right edge while the other columns scroll.
Long Ops row button labels wrap and buttons grow vertically rather than truncating their text.
Ops page tabs stay pinned below the app header, including when tabs wrap on mobile. A buffer
appears underneath only while the tabs are stuck, without changing the normal page spacing.
Reports, News, IPOs, and Companies search/filter/sort the full dataset on the server before
pagination; URL parameters preserve the table state across reloads and browser history.
Reports support date/text search and outlook filters; Companies also supports exact sector
filtering. Page sizes are bounded to 1-100, with the configured web size used by default.
Markets history and Delivery deliberately remain limited to the latest 30 predictions and 50
attempts; their local search, filters, sorting, and pagination are labeled with those limits.
No table fetches external data, recalculates scores, sends messages, or exposes recipient fields.

Today is served by React at `/dashboard/`, with a feature-filtered private endpoint at
`/api/app/today`. It shows the latest saved outlook and its actual target date, strength and
component scores, up to five saved cues, accuracy/baseline warnings, the strongest stories from
the last 36 hours, grouped IPOs, saved closes, and the latest report link. Disabled sections are
excluded by the server. News and IPO groups retain their existing four-item limits; the tables
search/filter/sort those bounded summaries, with links to the full React lists.
Successful logins open `/dashboard/` unless a safe same-host return URL was supplied.

Account opens `/account/`, showing subscription details, feature access, and a searchable,
filterable TanStack table of the latest 20 masked API tokens. Its private `/api/app/account`
endpoint counts all active tokens for issuance limits. Session-only, CSRF-protected POST actions
at `/api/app/account/tokens` and `/api/app/account/tokens/{id}/revoke` reuse existing issuance,
expiry, ownership, and audit rules. New secrets appear once in component-local state, never in
URLs, browser storage, or React Query caches; hide or leave the page to discard them.
Account remains accessible after subscription expiry. When public API access is disabled,
creation is denied, but existing tokens can still be viewed and revoked.

The React header includes an initials avatar with an account popover (username, email, role,
subscription status, Account details, and secure logout), plus an icon-only theme toggle.
Both controls work on mobile and desktop and retain keyboard-accessible labels and focus behavior.

React status and outlook tags, Ops badges (including summary cards), calendar badges, and
public-page tags share compact sizing: 1.5rem height, 0.8125rem text, and 0.5rem horizontal
padding. Their widths follow the label; status colors and Ops icons remain distinct.
Sizing is defined by shared tag tokens and styles in `frontend/src/styles/app.css`; Mantine
badges use the same styles through the app theme.

Staff can view task history at `/ops/runs/` and stored run diagnostics at
`/ops/runs/{id}/`. The TanStack history searches and filters all retained runs on the server
before pagination, with job/result/trigger filters and URL-preserved sorting and page size.
Active run details refresh every three seconds and stop on completion or error. Status badges
distinguish waiting, running, done, and failed runs. These read-only pages use staff-only
session endpoints under `/api/app/ops/runs`, with the same admin IP restrictions as `/ops/`.
Job execution and all other Ops controls now also have React pages under `/ops/`;
the retired Django template pages are no longer served.

The read-only Ops audit page is at `/ops/audit/`, backed by staff-only
`GET /api/app/ops/audit`. Its TanStack table searches recorded names, actions, targets, details,
and addresses across all retained records before pagination. Exact recorded-admin/action filters,
sorting, and page size are preserved in the URL. Actor names survive account renames/deletion;
details render as plain text, with timestamps in IST. Audit reads never create or alter events.

The full Ops workspace includes Overview, Jobs, Logs, Metrics, Users/access/subscriptions,
Logins/lockouts, Settings, Schedule, Feeds, Instruments, Configuration, and Backups.
Superuser actions reuse the original backend handlers, confirmations, validations, and audit
logging through private session/CSRF endpoints. Secret settings are never echoed; backup
restore retains its maintenance warnings, typed confirmation, and sign-out. Full lists use
server-side TanStack search, filters, sorting, and pagination; metric and recent-history
snapshots are explicitly bounded. The landing theme and strict CSP apply throughout.

Archived pages remain Django-rendered on the old subdomain only. Run
`pnpm --dir frontend build` to create the production bundle and
`pnpm --dir frontend build:legacy-css` to rebuild the stylesheet still used by Django templates.
The Docker image builds the React bundle automatically.

The private API is independent of the public `/api/v1/` switch and quota. It accepts active
session cookies only (Authorization headers are rejected), enforces CSRF for unsafe methods,
and never caches responses. `APP_API_RATE_LIMIT_PER_MINUTE` defaults to 300 requests per user;
production uses the same Redis-backed counters as the public API, with separate keys.
Feature and subscription restrictions remain enforced by Django on the linked pages.

After changing private API schemas, regenerate their committed OpenAPI document, TypeScript
types, and Zod response validators:

```bash
uv run python manage.py export_openapi --api app --output frontend/openapi/app.json
pnpm --dir frontend api:generate
pnpm --dir frontend format:check
pnpm --dir frontend typecheck
pnpm --dir frontend test
uv run pytest -q apps/api/tests/test_app.py
```

CI verifies both contract files and runs the frontend unit/component tests. The public API
schema remains separate and unchanged.

Code standards:

- Docstrings use the Google style. Every module, class, function, and method in `apps/` and
  `config/` (except tests and migrations) has one. The first line is a short summary that ends
  with a period. Functions have `Args`, `Returns` and `Raises` sections. A CI check enforces this
  for all new code (see the baseline in `docs/scripts/docstring_baseline.txt`).
- A comment explains why the code does something. It does not repeat what the code does.
- Fix the cause of a ruff or ty message. Use a `# noqa: CODE` or `# ty: ignore[rule]` comment only
  when the code is correct, and always give the reason after it.
- ruff and ty must report no errors. The commit hooks run both.

## REST API

The app has a read-only REST API at `/api/v1/`. A signed-in user makes an API token on the
Account page (the token is shown one time and the database keeps only its hash). Send it as
`Authorization: Bearer <token>`.

| Address | What |
| --- | --- |
| `/api/v1/docs` | Swagger UI (sign in first) |
| `/api/v1/openapi.json` | The OpenAPI 3.1 file |
| `/api/v1/health` | Health of the API (no sign-in) |
| `docs/openapi/v1.json` | A copy of the OpenAPI file in the repository |

Errors use `application/problem+json`. Inside `v1` the API can only add things. After a change
to the API, export the file again and commit it:

```bash
uv run python manage.py export_openapi --api-version v1 --output docs/openapi/v1.json
```

A test fails if the file is old. A superuser can turn the API off and set the limits on
Ops > Settings > REST API.

## Developer documentation

The self-hosted Docusaurus site is available at `/docs/` after you start the stack. It has the
guides (architecture, API, domains, operations, development) and a generated reference of every
HTTP endpoint, setting, scheduled job, task, command and Python function. Its source content is
in [`docs/docs/`](docs/docs/index.md).

To work on the site without Docker (Node.js 22 and Python 3.13):

```bash
cd docs
npm ci
npm start                  # http://localhost:3000/docs/
npm run reference:check    # the docstring gate
npm run build              # the production build, with link checks
```

The reference pages come from the source code. Git ignores them. `docs/docs/development/` explains
the docstring standard, the tests and the review steps.
