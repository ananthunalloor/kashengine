---
title: Self-hosting and deployment
---

# Self-hosting and deployment

The documentation site is part of the Compose deployment. Docusaurus builds static assets in a build stage. Nginx serves those assets on the private port `8080`. Caddy exposes them at `https://<SITE_ADDRESS>/docs/`. The docs container does not expose a host port and does not receive Django, database, Redis, or Telegram credentials.

## Development

After applying the Git patch, integrate it with the current checkout. This step is separate because the Compose and Caddy files can change independently of the documentation content.

```bash
python docs/scripts/integrate_self_hosted_docs.py --check
python docs/scripts/integrate_self_hosted_docs.py
cp .env.example .env.dev
docker compose config --quiet
docker compose up --build
```

The development override binds the Caddy ports to localhost. Open `https://localhost/docs/`. The app and docs use the same Caddy entry point so the same path routing and security policy can be checked locally. The browser can show a certificate warning because Caddy uses a local CA for `localhost`.

## Production setup

Use a Linux host with Docker Engine and the Compose plugin. The main application has a local LLM, so provision memory and disk according to the selected model. The README currently recommends 16 GB RAM or more for its production model; treat the actual model requirements as deployment-specific.

1. Configure DNS for the public hostname and permit inbound TCP 80/443 and UDP 443 if HTTP/3 is enabled.
2. Create the production environment file and protect it:

   ```bash
   cp .env.prod.example .env.prod
   chmod 600 .env.prod
   ```

3. Set `SITE_ADDRESS`, `ACME_EMAIL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, all required secrets, the database values, the Redis URL, and the LLM settings. Use real generated secrets. Do not commit `.env.prod`.
4. Build and start the stack:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     up -d --build
   ```

5. Create the application superuser and download the selected production model:

   ```bash
   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec web python manage.py createsuperuser

   docker compose --env-file .env.prod \
     -f docker-compose.yml -f docker-compose.prod.yml \
     exec ollama ollama pull llama3.1:8b
   ```

6. Open `https://<SITE_ADDRESS>/docs/` and confirm that navigation, images, stylesheet and JavaScript assets load without 404s or CSP violations.
7. Run the production Django deployment check with the required production environment and confirm that no actionable issues remain.
8. Test login lockout, admin IP restrictions, report generation, Telegram delivery, worker health, Beat's next-run times, backup creation, and restoration before relying on the deployment.

### Build-time site URL

The Compose build passes `DOCS_URL` to Docusaurus. It is built as `https://${SITE_ADDRESS}` by default and uses `/docs/` as its base path. Keep the `baseUrl` and Caddy's `/docs/` path stripping in sync. If the documentation is moved to a separate hostname or root path, update the Docusaurus config, the build argument, Caddy routing, CSP policy, and deployment tests together.

### Updating only documentation

After updating documentation files or Python docstrings:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build docs caddy
```

Compose rebuilds the documentation image from the same source checkout. Caddy is included so it is restarted if its configuration changed. If the Caddy config did not change, a docs-only rebuild is sufficient:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --build docs
```

Check service health and logs after a rebuild:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml ps

docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 docs caddy
```

### Deploy rollback

Keep the previously working image or previous Git revision available. If the site build fails, Compose should not replace the healthy running docs container with a successful new version. If the new static site loads incorrectly, roll back the docs source to the last known-good revision and rebuild the image. Do not roll back database migrations unless the migration explicitly supports reversal and the recovery plan accounts for writes made after deployment.

## Edge and container constraints

- Only Caddy publishes host ports.
- The docs service belongs on `proxy` in production; do not attach it to `backend` or `egress` without a documented need.
- Nginx runs as the unprivileged `nginx` user, listens on 8080, and writes temporary state under `/tmp`.
- The final docs image serves static output only. Do not add an application runtime or secrets to it.
- Do not mount the host source tree into the production docs container.
- Keep Caddy's `caddy_data` volume. It stores TLS certificate state.
- Logs are sent to stdout/stderr for Compose log rotation.

## Local build without Docker

```bash
cd docs
npm install
npm run api:check
npm run build
npm run serve
```

The site is served at port 8080 by this package script, but the public production URL remains `/docs/` behind Caddy. Never bind the development server to an untrusted network.
