---
title: Development workflow
sidebar_label: Workflow
description: Where code belongs, the checklist for a change, migrations, API changes, and patch delivery.
---

# Development workflow

## Put the code in the app that owns the data

A rule goes next to the data that it governs. News parsing is in `news`. The market prediction is
in `markets`. The IPO score is in `ipos`. The validation of settings is in `siteconfig`. The
operator controls are in `ops`. A low-level app does not import a web view.

A request is thin:

1. A view checks access and the input.
2. A form or a service checks the rules of the domain.
3. A service or a model changes the data.
4. A Celery task does the work that takes long.
5. A template shows the result. It does not compute a decision.

## Checklist for a change

- Find the model, service, task, view, template, setting and tests that the change touches.
- Write the expected behavior first.
- Check the input at the boundary. Use a database constraint for a rule that must hold when two
  requests come at the same time.
- Put an external call behind a small function that a test can replace. Set a timeout. Handle
  each provider error.
- Write the docstrings ([standard](./docstring-standard.md)).
- Write tests: valid input, invalid input, limits, and failure.
- If you add a setting, decide where it belongs:
  - A value that an operator may change goes in `apps/siteconfig/registry.py`, and code reads it
    with `conf`.
  - A value that decides how the process starts stays in the environment. Add it to
    `.env.example` and `.env.prod.example`.
- If an Ops action sends a message or replaces data, use the confirmation text of the job and the
  superuser check.
- If you add a Celery task, give it a `name` and a `soft_time_limit`. If a user may start it,
  add it to the job list in `apps/ops/jobs.py`. If it runs on a schedule, add it to
  `apps/ops/defaults.py` and write a migration for existing databases.
- Run the checks and read the diff.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
cd docs && npm run reference:check && npm run build
```

[Pre-commit](https://pre-commit.com) runs Ruff, the file checks and `ty` before each commit.
CI (`.github/workflows/ci.yml`) runs all the checks above for each pull request.

## React migration

The authenticated React preview is served by Django at `/app/`. Existing subscriber and Ops
pages remain server-rendered until their React replacements reach parity. Start Vite with
`pnpm --dir frontend dev` alongside Django, or use the frontend service in the dev Compose file.
Production uses the Vite manifest and built assets included in the Python image.

Today opens `/app/dashboard/`, backed by the session-only `/api/app/today` endpoint.
It requires an active subscription when that rule is enabled, but is not a separate feature:
Markets, News, IPOs, and Reports sections are independently authorized before their queries
run. Disabled sections return null, not hidden data. The preview preserves the existing
36-hour news window, ranking/deduplication, four-story/group limits, mutually exclusive IPO
groups, configured quotes, and latest saved report. The latest outlook keeps its actual target
date, five strongest saved cues and their trading dates, notes, component scores, and baseline/
small-sample caveats. Reads do not fetch, score, evaluate, or send anything. Bounded summaries
use local TanStack tables and shared metric colors; full-list links stay inside React.
The original `/dashboard/` and login redirect remain unchanged.

Account opens `/app/account/` and reads `/api/app/account`, including subscription details,
feature access, the latest 20 owner-scoped masked token rows, and the full active-token count.
Its TanStack tables provide local search, filters, sorting, and pagination over these bounded
rows. The preview and endpoint remain available after subscription expiry. POST
`/api/app/account/tokens` creates a token; POST `/api/app/account/tokens/{id}/revoke` revokes
only the current user's token. Both require session-cookie authentication and CSRF, reuse
existing token services, and audit only masked prefixes. Token names and contact text are
rendered as text, not HTML. No hash or password stamp is serialized.

The creation response contains a one-time secret and is marked `private, no-store`. The client
uses imperative writes rather than cached React Query mutations, with no automatic retries;
the secret lives only in component-local state until hidden or unmounted. It never enters
query caches, URLs, or browser storage. If creation succeeds but metadata refresh fails,
the page retains the secret and explicitly reports the partial success. When the public API
is disabled, creation is denied, but masked metadata and revocation remain available
intentionally, unlike the legacy page's hidden API section. The original `/account/` remains
unchanged apart from sharing the token-row limit.

Staff task history opens `/app/ops/runs/`, with details at `/app/ops/runs/{id}/`. The private
GET endpoints `/api/app/ops/runs` and `/api/app/ops/runs/{id}` use `OpsSession`: the existing
session/CSRF/rate-limit rules plus the same `is_staff` flag as Django Ops. Non-staff are rejected
before operational queries; subscriptions and the public API switch do not gate staff reads.
Direct preview URLs are staff-protected too. Caddy applies `ADMIN_ALLOWED_IPS` to `/app/ops`
and `/api/app/ops` and their children, not just the original `/ops` routes. Deploy the updated
proxy configuration alongside this preview.

The TanStack run table searches job labels, task names/IDs, and triggering usernames, with the
legacy exact job/result/trigger filters, sorting, and `OPS_PAGE_SIZE` pagination (override 1-100).
All processing happens server-side before pagination; URL state supports reloads and history.
The list excludes arguments, output, and diagnostics. Detail reads expose the same stored data
as the legacy staff-only page, rendered as plain text with IST times and the shared legacy
duration formatter. Waiting/running details poll every three seconds while visible and stop
when terminal, on errors, or on navigation. Failed refreshes explicitly hide stale operational
data, with manual retry for recoverable errors. Neither endpoint dispatches a job, calls
external services, or writes audit events. Job execution and other Ops pages remain Django
links; `/ops/runs/` and its original details remain available.

The audit trail preview opens `/app/ops/audit/` and reads `GET /api/app/ops/audit` with the
same `OpsSession` staff check and Caddy IP restrictions. All legacy display fields are retained:
time, recorded actor name, action, target, detail, and nullable address. Names come from the
event snapshot rather than the current user record, so renames/deletions do not change history.
The API serializes only these fields and the event ID, not user/session/token objects.

Search matches all text display fields and addresses. Exact actor/action filters use globally
distinct choices, independent of the current search. Whitelisted display-column sorting uses
nulls-last ordering and stable ID ties; default ordering remains newest-first. Pagination uses
`OPS_PAGE_SIZE` with an optional 1-100 override. The TanStack table keeps filters, search, sort,
and page size in the URL. Detail text is escaped and preserves line breaks, never HTML.
Background permission or refresh errors hide stale audit rows and display explicit recovery.
The page is read-only, has no polling, and never creates audit events. `/ops/audit/` is unchanged.

The private `/api/app/session` endpoint supplies the current user, allowed features, subscription
notice, and navigation. It reuses Django's navigation/access rules, accepts session cookies only,
and rejects Authorization headers. It is available even when the public API is disabled, and
has a separate per-user request budget (`APP_API_RATE_LIMIT_PER_MINUTE`, default 300).
It returns `401` rather than redirecting anonymous callers and marks every response `no-store`.
Unsafe private API methods use Ninja's CSRF-enabled cookie authentication.

The header's initials avatar opens a non-modal account popover with the current session's
username, email, role, subscription state, Account link, and CSRF-protected logout form.
Email is returned only for the current authenticated session, with an empty value when unset.
The popover focuses its Account link on opening, closes on Escape (restoring avatar focus),
outside pointer/focus, or route changes, and uses static CSS rather than runtime style injection.
The icon-only sun/moon control keeps an accessible label and a next-theme tooltip.

The browser client validates session responses against generated Zod schemas, sends CSRF tokens
for writes, and redirects expired sessions to Django login with the current return URL.
Reports opens `/app/reports/`, with a paginated list and detail pages at `/app/reports/YYYY-MM-DD/`.
The preview uses `/api/app/reports` and `/api/app/reports/{day}` with session-only, Reports-feature
authentication. It retains the original text-rendering and score-formatting helpers, adjacent
reports, and delivery history. Delivery recipients are excluded; only staff receive error details.
The existing `/reports/` pages remain unchanged for comparison. News opens `/app/news/` and reads
the session-only `/api/app/news` endpoint. It reuses `news_queryset` and `news_sources`, preserving
search over headlines and summaries, score thresholds, source choices, and the web page size.
Article links open in a new tab with `noopener noreferrer`; non-HTTP(S) links render as text.
Scores and explanations are plain text, with publication times displayed in IST. Search is
debounced by 300 ms, selects apply immediately, and filter changes reset pagination. Query
parameters preserve filters across bookmarks and browser history. The original `/news/` page is
unchanged. Other navigation links still open
the existing Django pages. Direct preview URLs and API requests both enforce access rules.

IPOs opens `/app/ipos/`, with issue details at `/app/ipos/{id}/`. The private `/api/app/ipos` and
`/api/app/ipos/{id}` endpoints reuse `ipo_queryset`, `ipo_facts`, and existing number-formatting
helpers. The default Active list excludes listed issues and preserves the original status
ordering. Search, board, verdict, and status filters are stored in the URL; search is debounced
and filter changes reset pagination. Saved verdict signals, original units, missing values,
metric freshness, and scored timestamps are preserved. No read endpoint refreshes metrics or
recalculates a verdict. The original `/ipos/` list/detail pages are unchanged.

Markets opens `/app/markets/`. Its private `/api/app/markets` endpoint reuses `accuracy_stats`,
`latest_quotes`, and `prediction_history` (newest 30), with existing percentage and strength
formatting. The preview preserves the common-direction baseline, small-sample warning, pending
count, and all four evaluation states. Saved closes always show their exchange-local trading
date; missing changes are not displayed as zero. Both preview and API enforce the Markets
feature and subscription rules. No read refreshes prices or evaluates results, and the original
`/markets/` page is unchanged.

Companies opens `/app/companies/`, backed by the session-only `/api/app/companies` endpoint.
It reuses `company_queryset` for name/symbol/sector search and alphabetical ordering. Only
directory display fields are returned, not aliases or scraped data. Search and pagination live
in the URL; debounced typing preserves focus, resets the page, and cancels pending updates on
navigation. Last-fetched dates use IST, and source links accept only absolute HTTP(S) URLs.
Direct preview and API requests enforce Companies access rules. Reads never refresh company
data, and the original `/companies/` page remains unchanged.

Delivery opens `/app/delivery/`, using the private `/api/app/delivery` endpoint and the same
`latest_deliveries` query as the original page (newest 50 attempts). Configuration exposes only
the count of nonempty Telegram chats, never chat IDs or bot credentials. Recipients are not
serialized, and diagnostics are staff-only. Attempts without a report retain the existing
"Test" label, including deleted reports. Report links target the React detail route and are
omitted when the Reports feature is unavailable. The preview has no send/retry-write actions;
reading never sends messages. Both routes enforce Delivery access; `/delivery/` is unchanged.

### Table and icon conventions

Use the shared `DataTable` (`frontend/src/shared/ui/DataTable.tsx`) for tabular lists, with
React Icons imported from `react-icons/lu`. Decorative SVGs are hidden from assistive technology;
icon-only actions retain accessible names. Sorting uses keyboard-accessible header buttons and
`aria-sort`. Table panels contain their own horizontal scrolling region and pagination.

Reports, News, IPOs, and Companies use manual TanStack pagination/filtering/sorting. The private
API validates a per-resource sort allowlist and optional `page_size` (1-100), applies filters and
stable sorting to the full queryset, then paginates. Empty sorting retains the legacy ordering;
nulls sort last in both directions. IPO GMP sorts by its percentage, not rupee amount or display
text. Search/filter/sort/page-size changes reset to page one and cancel pending search timers.
URL search schemas preserve bookmarks and back/forward navigation. Do not locally sort or filter
one server page as if it were the whole dataset.

Bounded overviews (latest 30 predictions, latest 50 delivery attempts), configured market closes,
and detail tables use local TanStack row models. Keep the history limits visible, sort formatted
numeric values via numeric accessors, and preserve missing values rather than inventing zeroes.
The API continues to redact diagnostics for members and exclude recipient identifiers.

Use `MetricValue` for signed changes/differences, IPO sentiment scores, and prediction strength
in tables and detail views. Gains are green, losses red, and zero/missing values neutral; retain
the original signs and units. Signed scores use the displayed neutral midpoint of 5.5/10.
Strength is independent of direction: green at 6.4/10 or above (the existing 0.6 high-confidence
cutoff), amber below, with a visible `StrengthLegend`. Never color a price, subscription multiple,
or relevance value as though it were a signed gain. News relevance uses `MetricValue` with
`kind="relevance"`: green at 6.4/10 or above, amber below, and missing values neutral.
Its labels explain high/lower relevance rather than positive/negative market direction.
Colors support both themes.

After changing the private schemas:

```bash
uv run python manage.py export_openapi --api app --output frontend/openapi/app.json
pnpm --dir frontend api:generate
pnpm --dir frontend format:check
pnpm --dir frontend test
pnpm --dir frontend build
uv run pytest -q apps/api/tests/test_app*.py
```

Do not put UI-only endpoints in `/api/v1/`: its public compatibility contract is unchanged.
CI checks the committed private OpenAPI document and generated TypeScript/Zod output separately.

The shared theme provider disables Mantine's runtime style elements. Use static CSS for
responsive layout instead of Mantine's AppShell or responsive style props: those generate
`<style>` elements that the enforced `style-src 'self'` policy rejects. Mantine's static
stylesheet supplies the default theme variables; inline style attributes remain permitted by
the existing `style-src-attr` policy. Never relax CSP to make a component render.

Landing and React share `static/css/brand-tokens.css`: update the shared palette there, not in
two independent themes. The landing stylesheet aliases these tokens, and Vite bundles them into
the React stylesheet. React adds dark-mode overrides in `frontend/src/styles/app.css`; new users
start in the landing page's light theme and existing saved preferences are respected.

## Database migrations

- Change the model, then run `makemigrations`. Read the migration.
- Do not edit a migration that is already in `main`.
- A migration that adds first data must be safe to run once on a new database.
- Before you deploy, take a [backup](../operations/backups-and-recovery.md) and decide how you
  will go back or go forward if the migration fails.

## Change the HTTP API

The API is a contract. Inside `v1` you may only add things. See
[Versioning](../api/versioning.md).

1. Change the router in `apps/api/v1/` and the schemas in `apps/api/v1/schemas.py`. Describe
   every field with `Field(description=...)`. Write the docstring of the endpoint for the API
   user.
2. Export the OpenAPI file:

   ```bash
   uv run python manage.py export_openapi --output docs/openapi/v1.json
   ```

3. Run the tests. `apps/api/tests/test_openapi.py` fails when the file is old, when an operation
   has no summary or description, and when a response field has no description.
4. Raise the minor number in `apps/api/versions.py` and write the change in the
   [changelog](../api/changelog.md).
5. CI runs `docs/scripts/openapi_compat.py` against the file on `main`. A breaking change fails.

## Patch delivery

To share work as a patch file, make it from a known base commit:

```bash
git format-patch origin/main..HEAD -o patches/
git apply --check patches/*.patch      # on the other checkout
git am patches/*.patch
```

Tell the receiver the base commit. Do not put unrelated changes in one patch.
