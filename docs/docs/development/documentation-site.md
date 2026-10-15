---
title: Documentation site
sidebar_label: Documentation site
description: How this site is built, how the reference pages are generated, and how CI keeps them true.
---

# Documentation site

The site uses [Docusaurus](https://docusaurus.io) 3. It is served under `/docs/` by the `docs`
service (nginx). Caddy sends the path `/docs` to that service.

## Files

| Path | What |
| --- | --- |
| `docs/docs/` | The guides (Markdown). You edit these by hand. |
| `docs/docs/reference/generated/` | The generated pages. **Do not edit them.** Git ignores them. |
| `docs/openapi/v1.json` | The OpenAPI file. The code exports it. A test keeps it current. |
| `docs/scripts/generate_reference.py` | The generator. It reads the source with `ast` and never runs project code. |
| `docs/scripts/docgen/` | The parts of the generator: docstring parser, inventory, checks, renderers. |
| `docs/scripts/openapi_compat.py` | Finds breaking changes between two OpenAPI files. |
| `docs/scripts/csp_hashes.py` | Makes the Content-Security-Policy of the site (see below). |
| `docs/docusaurus.config.js`, `docs/sidebars.js` | The site settings and the sidebars. |
| `docs/Dockerfile`, `docs/nginx.conf` | The image of the `docs` service. |

## Edit the guides

```bash
cd docs
npm ci
npm start          # make the generated pages, then start the site at http://localhost:3000/docs/
```

Edit a Markdown file under `docs/docs/`. The build fails on a broken link, on a broken anchor and
on an MDX error. Write plain Markdown. Put code in backticks, because `<`, `>`, `{` and `}` are
special in MDX.

Add a new page to `docs/sidebars.js`.

## What the generator makes

`npm run reference:generate` runs `python docs/scripts/generate_reference.py`. It writes:

| Folder | Pages | Source |
| --- | --- | --- |
| `http/` | One page for each tag of the API, and a page of the schemas. | `docs/openapi/v1.json` |
| `python/` | One page for each module, grouped by app, and a coverage page. | The docstrings. |
| `system/` | Settings, schedule, jobs, tasks, commands, routes. | `config/settings/*.py`, `apps/siteconfig/registry.py`, `apps/ops/defaults.py`, `apps/ops/jobs.py`, `@shared_task` decorators, `management/commands`, `urls.py` files. |

The generator also copies the OpenAPI file to `docs/static/openapi/v1.json`, so the site serves
it at `/docs/openapi/v1.json`.

Every Python reference page has a link to the source line. The links use the Git reference from
`DOCS_SOURCE_REF` (the build argument of the image, `main` by default).

### Options

```bash
python docs/scripts/generate_reference.py --check       # exit 1 on a new docstring gap (see the baseline)
python docs/scripts/generate_reference.py --write-baseline   # save the current gaps
python docs/scripts/generate_reference.py --list        # print the backlog
python docs/scripts/generate_reference.py --no-write    # do not write pages
python docs/scripts/generate_reference.py --source apps/ipos --ref my-branch
```

## CI

`.github/workflows/ci.yml` runs the Python checks, the tests, `npm run reference:check`, the
OpenAPI compatibility check, and `npm run build`.

## Security of the site

- The `docs` image has no application code, no secret and no database access.
- nginx sets a strict Content-Security-Policy. Docusaurus puts two small inline scripts in each
  page. `csp_hashes.py` reads the built pages and lists the SHA-256 hash of each distinct inline
  script, so the policy allows those scripts and no other inline script.
- Caddy does not add a policy for `/docs`. It adds the other security headers.
- The site has `noIndex` on, so search engines do not list it.
- Search is local (`@easyops-cn/docusaurus-search-local`). The browser loads no third-party
  script and no external font.
- A superuser can limit the site to some addresses with `DOCS_ALLOWED_IPS`. The default is open.

## Update dependencies

The versions are exact in `package.json`, and `package-lock.json` is in Git. The image uses
`npm ci`. To update a package, run `npm install <package>@<version> --save-exact`, run
`npm run build`, and commit both files.
