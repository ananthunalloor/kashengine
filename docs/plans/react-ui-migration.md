# Plan: migrate the web UI to React

Status: canonical React cutover complete; Django UI archived · Last updated: 2026-10-19

React now serves all subscriber and Ops pages at the original URLs, including `/` and `/login/`.
The `/app/` prefix was removed. Legacy Django templates and actions are isolated at
`old.${SITE_ADDRESS}`, guarded by active-superuser authorization with a dedicated archive
login and visible Archived notices. Django Admin, API docs, and the documentation site remain
outside the migration. The architecture and phases below record the original proposal.

## 1. Goal and scope

Replace the Django-template + Datastar UI (`apps/web/templates`, `apps/ops/templates`) with a
React single-page application, without changing the Python domain logic, the public `/api/v1`
contract, or the security posture (Caddy, CSP, IP allow-lists, session auth, django-axes).

In scope: Today dashboard, Reports, News, IPOs, Markets, Companies, Delivery, Account (API
tokens), all Ops pages, landing, login, and access/lockout screens.

Original product URLs now serve React; Django pages are available only on the archive hostname.
Logout remains a native CSRF-protected Django POST rather than a separate screen.
`/admin/`, Swagger at `/api/v1/docs`, and Docusaurus at `/docs/` are not being replaced.

### Current state (what the plan starts from)

| Area | Today |
| --- | --- |
| Pages | 13 web views (`apps/web/views.py`), ~35 Ops routes (`apps/ops/urls.py`), ~45 templates |
| Interactivity | Datastar from `cdn.jsdelivr.net` for filters/pagers (news, IPOs, companies) and Ops panels (health refresh every 15 s, logs, runs) |
| CSS | Tailwind v4 CLI in `frontend/` → `static/css/app.css`; tokens as CSS vars (`--paper`, `--ink`, `--gain`, …) with light/dark via `data-theme` |
| API | `/api/v1` (django-ninja): read-only, public, semver-guarded by `docs/scripts/openapi_compat.py`, bearer token **or** session cookie, rate-limited per user |
| Missing API | Dashboard aggregate, account token create/revoke, every Ops read/write action |
| Tooling | Python-only `pre-commit`; CI jobs `python`, `docs`, `images`; `docs/` uses npm |
| CSP | `script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval'` (because of Datastar) |

## 2. Key decisions

| # | Decision | Choice | Why |
| --- | --- | --- | --- |
| D1 | Component library | **Mantine** (v8+) | CSS-only styling (no runtime CSS-in-JS), so it fits the strict `style-src 'self'` CSP; MUI's Emotion needs `<style>` injection + nonces. Mantine's CSS layers coexist cleanly with Tailwind v4. Ships accessible primitives (Modal, Menu, Combobox, AppShell), `@mantine/dates`, `@mantine/notifications`. |
| D2 | App shape | **Vite SPA + TanStack Router** (file-based), **not TanStack Start** | Django already owns sessions, CSRF, login, axes, and permissions. Start would add a Node SSR server to prod (new container, new network path, duplicated auth). SEO-relevant pages stay Django-rendered. |
| D3 | Hosting | Django serves the SPA shell (`django-vite`), WhiteNoise serves hashed assets | Same origin → session cookie + CSRF just work; the login middleware still redirects anonymous users before the shell loads; Caddy rules (`/ops` IP allow-list) keep applying because URLs do not change. |
| D4 | URLs | **Same paths** as today (`/dashboard/`, `/news/`, `/ops/runs/`…) | Bookmarks, Caddy rules, and docs stay valid; enables per-route strangler cutover. |
| D5 | Backend for the UI | New private **`/api/app/`** NinjaAPI (BFF) next to `/api/v1` | Ops/account/dashboard endpoints are UI-internal; they must not enter the public semver contract or compat check. Separate rate-limit budget; session-only auth with CSRF. |
| D6 | Typed contracts | OpenAPI → **`@hey-api/openapi-ts`** (types + SDK + TanStack Query options + Zod) | Single source of truth is the Pydantic schemas in Django; generated client is committed and drift-checked in CI. |
| D7 | Hooks | Keep the **`pre-commit` framework** (add `pre-push` stage), no Husky | One hook manager for Python and TS; already installed for contributors. |
| D8 | Package manager | **pnpm** for `frontend/` (lockfile committed, `packageManager` field + Corepack) | Requirement. `docs/` stays on npm (out of scope; optional follow-up). |
| D9 | Charts | **TanStack Charts** (`react-charts`) behind a `features/*/charts` adapter; fallback `@mantine/charts` | TanStack Charts is still beta; the adapter keeps the swap cheap. Decide in the Phase 0 spike. |

## 3. Target architecture

```
Browser ──https──▶ Caddy ──▶ Django (gunicorn)
                              ├─ /, /login, /admin, /api/v1/docs   (templates, unchanged)
                              ├─ /dashboard/…, /ops/…              (SPA shell via django-vite)
                              ├─ /static/app/assets/*.js|css       (WhiteNoise, immutable)
                              ├─ /api/v1/…   public contract (unchanged)
                              └─ /api/app/…  private BFF for the SPA (session + CSRF)
```

Dev: `pnpm dev` (Vite on `127.0.0.1:5173`) serves modules + HMR; Django renders the shell with
`django-vite` in dev mode (injects `@vite/client`). You browse Django/Caddy as today, so login
redirects and cookies behave exactly as in prod, and React Fast Refresh + Tailwind/CSS HMR work.

### Auth and security

- Session cookie only for `/api/app/`; mutating calls send `X-CSRFToken` (read from the
  `csrftoken` cookie by the API client). Bearer tokens are rejected there.
- `/api/app/ops/*` checks `is_staff` (read) / `is_superuser` (write) with the **same**
  decorators/services as `apps/ops/permissions.py`, writes the same audit events, and is added
  to the Caddy `@admin_denied` matcher (`/api/app/ops /api/app/ops/*`).
- Feature gating: `GET /api/app/session` (or `/api/v1/me`) returns `features`, `is_staff`,
  subscription state → drives nav and route `beforeLoad` guards. The server still enforces 403;
  the client only hides.
- 401 from any call → redirect to `/login/?next=<current>`; 403 `feature_not_available` → the
  in-app "Not on your account" view.
- CSP after cutover: drop `https://cdn.jsdelivr.net` and `'unsafe-eval'`; keep
  `style-src 'self'` (Mantine/Tailwind are static CSS) and `style-src-attr 'unsafe-inline'`
  (Mantine style props). Dev keeps Report-Only and adds `ws://localhost:5173` to `connect-src`.

## 4. Repository layout

`frontend/` becomes the React app. The existing Tailwind CLI build for the remaining Django
templates moves into it as `pnpm build:legacy-css`, fed by the **same token source**, so both
UIs share colours during the transition.

```
frontend/
  package.json            # "packageManager": "pnpm@<pinned>"
  pnpm-lock.yaml
  tsconfig.json  tsconfig.app.json  tsconfig.node.json
  vite.config.ts
  .oxlintrc.json  .oxfmtrc.json
  openapi/                # app.json + v1.json (exported by Django)
  index.html              # used only by `vite preview`/tests; prod shell is Django
  src/
    main.tsx              # createRoot, providers, router
    app/
      providers/          # AppProviders: Theme, Query, Router, Notifications, ErrorBoundary
      router.tsx          # createRouter, context { queryClient, session }
      query-client.ts     # defaults: staleTime, retry policy by error kind
    routes/               # TanStack Router file routes (thin: loaders + lazy components)
      __root.tsx
      _authed.tsx         # layout route: AppShell + session guard
      _authed/dashboard.tsx
      _authed/news.tsx    # validateSearch: zod filters (replaces Datastar signals)
      _authed/ipos/index.tsx  _authed/ipos/$ipoId.tsx
      _authed/ops/route.tsx   # staff guard + Ops sub-nav
      _authed/ops/runs/…
    features/             # one folder per domain; no cross-feature imports except via index.ts
      dashboard/ reports/ news/ ipos/ markets/ companies/ delivery/ account/
      ops/{overview,jobs,runs,logs,metrics,users,subscriptions,logins,audit,
           settings,schedule,feeds,instruments,config}/
        api/              # query/mutation option factories wrapping the generated SDK
        components/       # feature UI
        hooks/
        model/            # view-model mappers, formatters (pure, unit-tested)
        index.ts          # public surface of the feature
    shared/
      api/                # http client, CSRF, error mapping (problem+json → ApiError), generated/
      ui/                 # design-system wrappers over Mantine (DataTable, FilterBar, ScoreBadge,
                          #   Pager, EmptyState, PageHeader, ConfirmButton, VirtualList)
      lib/                # format (scores, INR, dates in IST), a11y helpers, hooks
      config/             # env (zod-validated import.meta.env)
      state/              # TanStack Store instances (UI-only state)
    theme/
      tokens/             # primitive.ts, semantic.ts, component.ts (source of truth)
      mantine-theme.ts    # createTheme from tokens
      css/tokens.css      # GENERATED: CSS vars for Tailwind @theme + legacy templates
      ThemeProvider.tsx   # MantineProvider + color-scheme manager + Tailwind dark variant
    styles/
      app.css             # @layer order, @import tailwindcss, @theme from tokens.css
      legacy.css          # old app.css entry for Django templates (removed in Phase 6)
    test/                 # vitest setup, MSW handlers generated from OpenAPI, a11y helpers
  e2e/                    # Playwright + @axe-core/playwright
```

Rules (enforced by Oxlint `import/no-restricted-paths`):
`routes → features → shared/theme`; features never import other features' internals;
`shared` never imports `features`.

## 5. Design system

### Token architecture (3 tiers)

1. **Primitive** — raw scales: `indigo.0–9`, `green.*`, `red.*`, `amber.*`, `slate.*`, spacing
   (4 px base), radii, font stacks (existing sans + Charter serif), type scale, shadows,
   z-index, motion durations, breakpoints (`xs 36em, sm 48em, md 62em, lg 75em, xl 88em`).
2. **Semantic** — the names the app already uses, per colour scheme: `paper, card, ink, muted,
   rule, accent, gain, loss, gain-soft, loss-soft, flat-soft, warn, warn-soft`, plus
   `focus-ring`, `danger`, `success`. Light/dark values copied from `frontend/app.css` first so
   the look does not change.
3. **Component** — e.g. `score-badge.{positive,neutral,negative}.{bg,fg}`, `table.row-hover`,
   `appshell.nav-width`.

`theme/tokens/*.ts` (typed `as const`) is the single source. A small script
(`pnpm tokens:build`, also a Vite plugin in dev for HMR) emits `css/tokens.css`:

- `:root` / `[data-mantine-color-scheme="dark"]` CSS variables,
- a Tailwind v4 `@theme` block mapping `--color-paper: var(--kash-paper)` etc.,
- Mantine consumes the same values via `createTheme({ colors, primaryColor, fontFamily,
  breakpoints, spacing, radius, other })` and a `cssVariablesResolver`.

CI checks that `tokens.css` is up to date and that every semantic fg/bg pair meets WCAG AA
contrast (4.5:1 text, 3:1 UI) in both schemes (unit test over the token table).

### Centralised theme provider

`ThemeProvider` = `MantineProvider` (theme + resolver + `defaultColorScheme="auto"`) +
`localStorageColorSchemeManager` + a `ColorSchemeToggle`. Tailwind dark variant is bound to the
same attribute: `@custom-variant dark (&:where([data-mantine-color-scheme=dark] *));` so
Mantine and Tailwind never disagree. Legacy templates switch from `data-theme` to the same
attribute in Phase 2 so the preference carries across both UIs.

### Mantine + Tailwind coexistence

```css
@layer theme, base, mantine, components, utilities;
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/preflight.css" layer(base);
@import "@mantine/core/styles.layer.css";
@import "tailwindcss/utilities.css" layer(utilities);
@import "../theme/css/tokens.css";
```

Convention: Mantine for components and behaviour; Tailwind utilities for layout/spacing on
app-level markup. No `!important`, no arbitrary hex colours (lint + review).

### Responsive

- Mantine `AppShell`: header + collapsible navbar (burger < `sm`), Ops sub-nav as a second
  navbar section.
- Mobile-first; tables use `DataTable` with column priority — low-priority columns hide < `md`,
  and rows switch to a stacked card layout < `sm`. Filters collapse into a `Drawer` on mobile.
- Playwright a11y/visual runs at 360, 768, 1280 px.

### Accessibility (WCAG 2.2 AA)

- Oxlint `jsx-a11y` plugin on `error`.
- Skip link, landmark roles, one `<h1>` per route; on navigation, move focus to the `<h1>` and
  announce the new title in a polite live region (router `onResolved`).
- Never colour-only meaning: gain/loss also show sign/arrow + text ("Up 1.2%").
- Score display (README "Score display") rendered as text "6.4/10" with an `aria-label`.
- Respect `prefers-reduced-motion` (Mantine `respectReducedMotion`).
- Interactive tables: sortable headers are buttons with `aria-sort`; pagination announces
  "Page 2 of 7".
- Forms: labels, `aria-describedby` errors, focus first invalid field on submit.
- `@axe-core/playwright` on every route in both colour schemes; zero serious/critical
  violations is a merge gate. Manual screen-reader pass (NVDA + VoiceOver) per phase.

## 6. API abstraction layer and typed contracts

```
Django Pydantic schemas ─▶ manage.py export_openapi ─▶ frontend/openapi/{v1,app}.json
   ─▶ @hey-api/openapi-ts ─▶ src/shared/api/generated/{types,sdk,zod,@tanstack/react-query}
   ─▶ features/*/api/*.ts  (query keys, options, mappers)  ─▶ components
```

- `shared/api/client.ts`: configured fetch client — base URL, `credentials: "same-origin"`,
  CSRF header on unsafe methods, `Accept: application/json`, `AbortSignal` support.
- `shared/api/errors.ts`: maps problem+json (`type`, `code`, `detail`, `instance`) into a
  discriminated union `ApiError = Unauthorized | Forbidden(feature) | RateLimited(retryAfter) |
  Validation(fields) | NotFound | Server | Network`. Query retry policy: never retry 4xx except
  429 (honour `Retry-After`).
- Runtime validation: Zod schemas validate responses in dev/test (fail loud) and are sampled in
  prod (log, do not crash) — catches drift between deploys.
- Feature APIs expose **query option factories** (`newsQueries.list(filters)`), not raw hooks,
  so the same options serve route `loader`s (`ensureQueryData`) and components
  (`useSuspenseQuery`).
- CI drift check: export OpenAPI → regenerate → `git diff --exit-code`.
- `export_openapi` gains an `--api app` option; `/api/app` is excluded from
  `openapi_compat.py` but must stay backwards compatible within one release (open tabs).

### Backend work required (`apps/api/app/`)

| Endpoint group | Purpose | Notes |
| --- | --- | --- |
| `GET /session` | user, staff/superuser flags, features, subscription notice, build hash | Replaces template context `nav`/`notice` |
| `GET /dashboard` | one aggregate for the Today page | Reuse `apps/web/queries.py` |
| `GET/POST/DELETE /account/tokens` | list/create/revoke API tokens | Reuse `apps/api/tokens.py`; show secret once |
| `GET /ops/health`, `/ops/metrics` | overview panel, 14-day series | Reuse `apps/ops/health.py`, `metrics.py` |
| `GET /ops/jobs`, `POST /ops/jobs/{key}/run` | jobs, run now (with `confirm`) | Superuser + audit, same guards as `views.job_run` |
| `GET /ops/runs`, `/ops/runs/{id}` | runs list/detail, cursor pagination | |
| `GET /ops/logs` | filtered tail, redaction kept server-side | Cursor for virtualised infinite scroll |
| `/ops/users…`, `/ops/subscriptions`, `/ops/logins`, `/ops/audit` | list/detail + actions (end sessions, revoke tokens, set active, access, subscription give/end, unlock) | Each POST → existing service + audit |
| `/ops/settings…`, `/ops/schedule…`, `/ops/feeds…`, `/ops/instruments…`, `/ops/config` | CRUD | Field-level validation errors for TanStack Form |

Every endpoint gets pytest coverage mirroring `apps/ops/tests` and the web tests, plus a
permissions matrix test (anonymous / user / staff / superuser / feature removed /
subscription locked). `/api/app` gets its own, higher rate-limit budget so SPA navigation and
Ops polling never consume a user's public API quota.

## 7. TanStack usage map

| Library | Use | Where |
| --- | --- | --- |
| **Router** | File-based typed routes, `validateSearch` (Zod) for all filters/pagination (URL is the state, replaces Datastar signals; links stay shareable), `beforeLoad` auth/feature/staff guards, loaders with `ensureQueryData`, route code splitting, pending/error components | All routes |
| **Query** | Server state, caching, `refetchInterval` (Ops health 15 s, paused when tab hidden), mutations with invalidation, optimistic toggles (feed/schedule on/off), `useInfiniteQuery` for logs/runs | All features |
| **Table** | Headless tables wrapped by `shared/ui/DataTable` (Mantine markup): server-side sort/filter/paginate bound to router search params, column visibility for responsive | News, IPOs, companies, delivery, runs, users, subscriptions, logins, audit, feeds, instruments, schedule |
| **Form** | Typed forms with Zod validators, server-error mapping, dirty tracking | Token create, Ops settings groups, schedule add/edit, instruments, user access/subscription, feed add |
| **Virtual** | Virtualised rows | Ops logs, run output, long news lists |
| **Pacer** | Debounce text filters (300 ms) before updating search params; throttle scroll/resize handlers; guard "Run now" double clicks | FilterBar, logs search, job actions |
| **Store** | Small cross-cutting UI state only: command palette, navbar collapsed, table density | `shared/state` (server state in Query, URL state in Router) |
| **Hotkeys** | `/` focus search, `g d` / `g n` / `g o` navigation, `Mod+K` command palette, `?` shortcut help | `app/` + FilterBar (fallback: Mantine `useHotkeys`) |
| **Charts** | Markets accuracy & prediction history, Ops metrics (14-day series), IPO GMP trend | Behind a chart adapter (D9) |
| **Start** | **Not used** (D2) | — |

## 8. Code quality tooling

### TypeScript (strict)

`tsconfig.app.json` highlights:

```jsonc
{
  "compilerOptions": {
    "target": "ES2022", "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext", "moduleResolution": "bundler", "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noPropertyAccessFromIndexSignature": true,
    "noUnusedLocals": true, "noUnusedParameters": true,
    "allowUnreachableCode": false, "allowUnusedLabels": false,
    "verbatimModuleSyntax": true, "isolatedModules": true,
    "erasableSyntaxOnly": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true, "noEmit": true,
    "paths": { "@/*": ["./src/*"] }
  }
}
```

Type check with `tsc -b` (evaluate `tsgo` for speed in Phase 0).

### Oxlint (strict)

`.oxlintrc.json` sketch:

```jsonc
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["typescript", "react", "react-perf", "jsx-a11y", "import", "unicorn", "promise", "vitest"],
  "categories": { "correctness": "error", "suspicious": "error", "perf": "error",
                  "pedantic": "warn", "style": "off", "restriction": "off" },
  "rules": {
    "react/rules-of-hooks": "error", "react-hooks/exhaustive-deps": "error",
    "typescript/no-explicit-any": "error", "typescript/no-non-null-assertion": "error",
    "typescript/consistent-type-imports": "error",
    "typescript/no-floating-promises": "error", "typescript/no-misused-promises": "error",
    "import/no-cycle": "error", "import/no-default-export": "error",
    "no-console": ["error", { "allow": ["warn", "error"] }],
    "eqeqeq": "error"
  },
  "overrides": [
    { "files": ["src/routes/**", "*.config.ts"], "rules": { "import/no-default-export": "off" } }
  ],
  "ignorePatterns": ["dist", "src/routeTree.gen.ts", "src/shared/api/generated/**"]
}
```

Run as `oxlint --type-aware --deny-warnings` (type-aware rules via `oxlint-tsgolint`), so
`pedantic` warnings also fail CI. Feature boundaries via `import/no-restricted-paths`.

### Oxfmt

`.oxfmtrc.json` (Prettier-compatible options: `printWidth 100`, double quotes, trailing commas;
Tailwind class sorting if supported). Formats `ts/tsx/json/css/md` under `frontend/`.
Generated files excluded. Phase 0 confirms Oxfmt maturity; fallback is Prettier with identical
options (script names stay the same, so hooks/CI do not change).

### Scripts (`frontend/package.json`)

| Script | Command |
| --- | --- |
| `dev` | `vite` |
| `build` | `pnpm tokens:build && tsc -b && vite build` |
| `build:legacy-css` | Tailwind build of `styles/legacy.css` → `../static/css/app.css` (until Phase 6) |
| `lint` / `lint:fix` | `oxlint --type-aware --deny-warnings` / `… --fix` |
| `format` / `format:check` | `oxfmt` / `oxfmt --check` |
| `typecheck` | `tsc -b` |
| `test` / `test:e2e` | `vitest run --coverage` / `playwright test` |
| `api:generate` / `api:check` | `openapi-ts` / `openapi-ts && git diff --exit-code src/shared/api/generated` |
| `tokens:build` / `tokens:check` | token CSS generation / drift check |
| `validate` | `format:check && lint && typecheck && test && api:check && tokens:check && build` |

### Git hooks (`.pre-commit-config.yaml`)

```yaml
default_install_hook_types: [pre-commit, pre-push]
default_stages: [pre-commit]
repos:
  # … existing Python hooks …
  - repo: local
    hooks:
      - id: oxfmt
        name: oxfmt (frontend)
        entry: pnpm --dir frontend exec oxfmt
        language: system
        files: ^frontend/.*\.(ts|tsx|js|json|css|md)$
        exclude: ^frontend/src/shared/api/generated/
      - id: oxlint
        name: oxlint (frontend)
        entry: pnpm --dir frontend exec oxlint --deny-warnings --fix
        language: system
        files: ^frontend/src/.*\.(ts|tsx)$
      - id: frontend-validate
        name: frontend validate (types, tests, contracts, build)
        entry: pnpm --dir frontend validate
        language: system
        files: ^(frontend/|apps/api/)
        pass_filenames: false
        stages: [pre-push]
      - id: pytest-api
        name: pytest (API)
        entry: uv run pytest -q apps/api
        language: system
        files: ^apps/(api|ops|web)/
        pass_filenames: false
        stages: [pre-push]
```

Pre-commit = fast, staged files only (format + lint with autofix). Pre-push = full validation.
README "Development tools" documents `pre-commit install` (hook types come from the config).

### CI (`.github/workflows/ci.yml`)

```yaml
  frontend:
    name: Frontend
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4          # version from packageManager
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm format:check
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm tokens:check
      - run: pnpm test
      - run: pnpm build

  contracts:   # Python + Node: export OpenAPI (v1 + app) with uv, then `pnpm api:check`

  e2e:
    needs: [frontend]
    # Postgres/Redis services, migrate + seed fixtures, Django with built assets,
    # `pnpm test:e2e` (Playwright + axe, 3 viewports, light/dark); upload report on failure.
```

Branch protection requires `Frontend`, `contracts`, and `e2e`. The `images` job also builds
the app image (which now has a Node build stage).

## 9. Testing strategy

| Level | Tool | Target |
| --- | --- | --- |
| Unit | Vitest | Formatters (score `1 + 4.5 × (s + 1)`, strength `1 + 9 × v`, INR, IST dates), mappers, token contrast. Score vectors come from a shared JSON fixture also used by pytest, so Python reports and the TS UI cannot drift. |
| Component | Vitest + Testing Library + MSW (handlers typed from the generated SDK) | DataTable, FilterBar, forms, guards |
| Contract | Generated-client drift check; Zod response validation in tests | |
| E2E + a11y | Playwright + axe | Every route; login → dashboard; Ops superuser actions; feature-removed user; subscription-locked user |
| Backend | pytest | Every `/api/app` endpoint + permission matrix |

Coverage gate: 80 % lines on `features/**/model` and `shared/**`.

## 10. Build and deployment

- `Dockerfile` gains a first stage `node:22-slim` → `corepack enable` → `pnpm install
  --frozen-lockfile` → `pnpm build`; `frontend/dist` (with Vite `manifest.json`) is copied into
  the Python image under `static/app/`, and `collectstatic` picks it up.
- Vite `base: "/static/app/"`, `build.manifest: true`; `django-vite` reads the manifest.
  Hashed assets get `Cache-Control: immutable` from WhiteNoise; the shell HTML is `no-cache`.
- `docker-compose.override.yml`: new `frontend` service (`node:22`, bind mount,
  `pnpm dev --host 0.0.0.0`, port `127.0.0.1:5173`); `DJANGO_VITE_DEV_MODE=true` for `web`.
- Caddyfile: add `/api/app/ops /api/app/ops/*` to `@admin_denied`; after cutover remove
  jsdelivr + `'unsafe-eval'` from the CSP; update `tests/test_deploy_config.py`.
- Source maps kept as CI artefacts only (not served).

## 11. Migration phases

Strangler pattern: each Django route switches from its template view to the SPA shell view
when its React page reaches parity. Rollback = revert that URL switch (one line per route).

| Phase | Work | Exit criteria | Size |
| --- | --- | --- | --- |
| **0. Spikes** (≈1 wk) | Mantine + Tailwind v4 layering under the strict CSP; Oxfmt + type-aware Oxlint stability; TanStack Charts vs `@mantine/charts`; TanStack Hotkeys/Pacer API check; django-vite HMR through Caddy | Findings appended to this doc; versions pinned | S |
| **1. Scaffold & tooling** | pnpm Vite React-TS app in `frontend/`; strict tsconfig; Oxlint/Oxfmt; Vitest/Playwright; pre-commit + pre-push hooks; CI jobs; legacy CSS build moved to `pnpm build:legacy-css`; npm lockfile removed | CI green on an empty app; `pre-commit run --all-files --hook-stage pre-push` passes | M |
| **2. Foundations** | Token pipeline + contrast tests; ThemeProvider + colour-scheme toggle (shared with legacy templates via attribute); AppShell, nav from session features, skip link, focus/announce on route change; Router + Query wiring; API client, error model, codegen; `shared/ui` kit (DataTable, FilterBar, Pager, ScoreBadge, EmptyState, ErrorState, ConfirmButton); Django SPA shell view + django-vite; Docker multi-stage build | A "kitchen sink" route passes axe; shell served with HMR in dev and from the prod image | L |
| **3. Backend enablement** | `/api/app` NinjaAPI: `session`, `dashboard`, `account/tokens`; OpenAPI export + codegen in CI; separate rate-limit budget; permission-matrix tests | Endpoints tested; `contracts` job green | M |
| **4. Subscriber pages** | In order: Reports (list/detail) → News → IPOs (list/detail) → Companies → Markets (+ charts) → Delivery → Dashboard → Account (tokens). Filters in URL search params, debounced; pagination parity with the Datastar pages | Per page: parity checklist, e2e + axe green, URL switched, old template deleted | L |
| **5. Ops** | `/api/app/ops/*` endpoints, then pages: read-only first (Overview with 15 s polling, Runs, Logs virtualised, Metrics charts, Audit, Logins, Config, Subscriptions, Users) → mutations (Jobs run-now, user actions, settings groups, schedule, feeds, instruments) with confirmations + audit; Caddy rule update; security review before cutover | Staff / superuser / non-staff e2e matrix green; audit entries identical to the template flow | XL |
| **6. Cutover & cleanup** | Remove Datastar (`apps/web/datastar.py`, `datastar_src`), unused templates/templatetags/views; tighten CSP; update README, `docs/docs/architecture/*`, `docs/docs/development/workflow.md`, `docs/docs/operations/dashboard.md`; decide whether landing/login move to React | No template left for migrated paths; CSP without `unsafe-eval`; docs build green | M |

Per-page parity checklist: same data and ordering · same filters and defaults · feature gate /
403 behaviour · subscription notice · empty / error / loading states · keyboard-only use ·
mobile layout · light/dark · score formatting · no-JS fallback consciously dropped (documented).

## 12. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Oxfmt / type-aware Oxlint / TanStack Charts / Hotkeys not production-ready | Phase 0 spikes; stable script names, so swapping to Prettier, Mantine charts, or Mantine `useHotkeys` is local |
| Ops endpoints widen the attack surface | Same permission decorators + services as today, Caddy IP allow-list extended, CSRF on all writes, permission-matrix tests, security review before Phase 5 cutover |
| Public API contract polluted by UI needs | Separate `/api/app` (D5), excluded from `openapi_compat.py` |
| API rate limit hit by SPA traffic/polling | Separate budget for `/api/app`; polling pauses on hidden tabs |
| Loss of no-JS support on filter pages | Accepted trade-off; landing/login stay server-rendered |
| Two UIs diverging visually during migration | Shared token source and colour-scheme attribute from Phase 2 |
| Stale tabs after a deploy calling a changed `/api/app` | Additive changes within a release; `/session` returns the build hash and the client prompts a reload |
| Score formatting drift between Python reports and the TS UI | Shared JSON test vectors run in pytest and Vitest |

## 13. Open questions

1. Should some `/api/app` endpoints (for example account tokens) later be promoted into
   `/api/v1` for third-party clients?
2. Does any user need no-JS access to the News/IPO filters? (The plan assumes no.)
3. Move the landing and login pages to React in Phase 6, or keep them server-rendered?
4. Should `docs/` also move from npm to pnpm for one toolchain?
