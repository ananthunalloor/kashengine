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
apps/       Django apps: news, companies, ipos, reports, delivery
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
| Admin site | Set `ADMIN_ALLOWED_IPS` to limit `/admin/` to your IP addresses or VPN range. |

Notes:

- Docker changes the firewall rules itself. A tool such as `ufw` does not block a port that Docker publishes. This is why no other service publishes a port.
- `ADMIN_ALLOWED_IPS` uses the client address that Caddy sees. With Docker and IPv6, Caddy can see the address of the Docker gateway. Test it from an allowed and from a blocked address.
- The Content-Security-Policy allows the Datastar script from `cdn.jsdelivr.net`. If you serve Datastar from another host, change `script-src` in `deploy/caddy/Caddyfile`. To test a policy change, set `CSP_HEADER=Content-Security-Policy-Report-Only` in `.env.prod` and read the browser console.
- Keep the `caddy_data` volume. It holds the certificate keys. Let's Encrypt limits how many new certificates you can get for a domain each week.
- There is no limit on login attempts yet. Use a long password for the login. A limit (for example `django-axes`) is a good next step.
- Run `python manage.py check --deploy` with the prod settings after each change to the settings. It must show no issues.

## Settings

| File | Use |
| --- | --- |
| `.env.example` | Template for dev. Copy to `.env.dev` |
| `.env.prod.example` | Template for prod. Copy to `.env.prod` |
| `.env.dev`, `.env.prod` | Real values. Not in Git |

The settings module is `config.settings.dev` or `config.settings.prod`.

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
