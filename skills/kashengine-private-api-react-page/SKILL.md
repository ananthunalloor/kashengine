---
name: kashengine-private-api-react-page
description: Add or change a private /api/app endpoint and the React page that consumes it in KashEngine, including OpenAPI export, hey-api TypeScript/Zod client regeneration, TanStack Router route, and React Query loader. Use for any UI-backed data change.
---

# Private API + React page

The private API (`apps/api/app/`) serves only the React app. Never put UI-only endpoints in the
public `/api/v1/` (see the `kashengine-public-api-v1` skill).

## Backend

1. Add or change the router module in `apps/api/app/<domain>.py` and schemas in
   `apps/api/app/schemas.py`. Register routers in `apps/api/app/api.py`.
2. Authorization: session cookie + CSRF for writes. Check the feature permission before any
   query; disabled sections return `null`, never hidden data. Staff Ops endpoints use `OpsSession`.
3. Server-backed lists: validate a per-resource sort allowlist and optional `page_size` (1-100),
   filter and stably sort the full queryset, then paginate (see `apps/api/app/tables.py`).
   Nulls sort last in both directions; empty sort keeps the legacy order.
4. Secrets (e.g. new API tokens) are returned once with `private, no-store`, audited only as
   masked prefixes, and never serialized as hashes.
5. Tests: `apps/api/tests/test_app*.py`.

## Regenerate the contract

```bash
uv run python manage.py export_openapi --api app --output frontend/openapi/app.json
pnpm --dir frontend api:generate      # writes src/shared/api/generated/{types,zod}.gen.ts
```

A Python test fails if `frontend/openapi/app.json` is stale; CI runs `pnpm api:check`.
Never hand-edit `src/shared/api/generated/`.

## Frontend layout

| Path | Role |
| --- | --- |
| `frontend/src/shared/api/<domain>.ts` | `queryOptions` factory + Zod-validated fetch |
| `frontend/src/routes/<path>.tsx` | TanStack file route (loader, search schema, pending/error) |
| `frontend/src/features/<domain>/` | Presentational page components + tests |
| `frontend/src/shared/ui/` | Shared components (`DataTable`, `MetricValue`, `AppStatus`, ...) |

### Query factory

```ts
export function marketsQuery() {
  return queryOptions({
    queryKey: ["app", "markets"],
    queryFn: async ({ signal }) => {
      const result = zMarkets.safeParse(await appRequest("/api/app/markets", { signal }));
      if (!result.success)
        throw new ApiError("contract", "The Markets response does not match this app. Reload the page.");
      return result.data;
    },
  });
}
```

### Route

```tsx
export const Route = createFileRoute("/news/")({
  validateSearch: (search) => newsSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(newsQuery(deps)),
  component: NewsPage,
  pendingComponent: () => <AppLoading withinShell label="news" />,
  errorComponent: (props) => <AppError {...props} withinShell section="News" />,
});
```

- URL search schemas (Zod) hold filters/sort/page so bookmarks and back/forward work.
- Filter/sort/page-size changes reset to page 1 and cancel pending search debounce timers.
- Feature components take typed props from `generated/types.gen` and call `usePageTitle`.
- Secret-bearing writes use imperative requests (no cached mutations, no retries); keep
  secrets in component state only, never in query cache, URL, or storage.
- Public (anonymous) screens use the `src/public.tsx` entry, not the authenticated router.
- If you add a product page, update the route inventory test in
  `apps/web/tests/test_public_preview.py`.

## Verify

```bash
pnpm --dir frontend format:check
pnpm --dir frontend api:check
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
uv run pytest -q apps/api/tests/test_app*.py
```

Follow the `kashengine-frontend-ui` skill for the component itself.
