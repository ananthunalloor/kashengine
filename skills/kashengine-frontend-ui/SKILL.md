---
name: kashengine-frontend-ui
description: Build or modify React UI in KashEngine's frontend (Mantine 8, TanStack Table/Router/Query, react-icons, CSP-safe styling). Use when writing components under frontend/src, tables, metric coloring, icons, layout, or theme changes.
---

# KashEngine frontend UI

Sources of truth: `frontend/UI_STANDARD.md` and the "Table and icon conventions" section of
`docs/docs/development/workflow.md`. Package manager: `pnpm` (run with `pnpm --dir frontend`).

## Layout and styling

- Use Mantine `Stack`, `Group`, `SimpleGrid`, `Grid`; no custom flex/grid markup for routine
  layouts. Page root is typically `<Stack gap="xl">`.
- Spacing scale from `src/app/uiStandard.ts`: `xs` control internals, `sm` inline items,
  `md` component internals, `lg` related sections, `xl` page sections, `xxl` major breaks.
- Custom CSS uses `--ui-*` variables in `src/styles/app.css`. No new literals for spacing,
  radius, or control size.
- **All corners square.** Never add rounded exceptions.
- Shared palette lives in `static/css/brand-tokens.css`; dark-mode overrides in
  `frontend/src/styles/app.css`.
- **CSP:** `style-src 'self'` is enforced and Mantine runtime style elements are disabled.
  Do not use Mantine `AppShell` or responsive style props; use static CSS for responsive layout.
  Inline `style` attributes are allowed. Never relax CSP to make something render.
- Pages render `AppFooter` outside the main landmark.

## Typography

- `Title` for headings (semantic order: one `order={1}` per page, sections `order={2}`),
  `Text` for body; `c="dimmed"` for secondary copy. No custom fonts, weights, letter spacing,
  or viewport-scaled sizes.

## Controls and icons

- Mantine buttons/forms only; icon-only actions use `ActionIcon` with an accessible label or
  tooltip and sizes from `uiStandard.controls.icon`.
- Icons from `react-icons/lu`. Decorative icons get `aria-hidden="true"`. Use
  `leftSection`/`rightSection` to align icons with labels. Never size all `svg` globally.
- Dates: `@mantine/dates`, ISO `YYYY-MM-DD` values, popover transitions disabled.

## Tables

- Always use `shared/ui/DataTable.tsx` (compact filter toolbar + shared pagination footer).
- Bounded local data (e.g. latest 30 predictions): pass `data`, `columns`, `filters`,
  `initialSort`, `label`. Keep history limits visible in the label/copy.
- Server-backed lists (Reports, News, IPOs, Companies): manual pagination/sort/filter via
  `filterControls` with `TableFilters` / `TableFilterField`. Never sort/filter one server page
  locally as if it were the whole dataset.
- Column `value` must be sortable (use `displayNumber(...)` for numbers); `render` handles display.
  Preserve missing values; never invent zeroes.
- Search inputs and selects keep accessible labels (visually hidden is fine).

## Metric coloring (`shared/ui/MetricValue.tsx`)

- `kind="change"` for signed changes: gain green, loss red, zero/missing neutral; keep signs/units.
- IPO sentiment scores: neutral midpoint 5.5/10.
- `kind="strength"`: green at 6.4/10 or above, amber below; show `<StrengthLegend />` nearby.
- `kind="relevance"` for news relevance: green at 6.4/10 or above, amber below.
- Never color prices, subscription multiples, or plain values as gains/losses.

## Accessibility

- Sections use `aria-labelledby` pointing at their heading `id`.
- Sorting headers are keyboard buttons with `aria-sort`.
- Empty states use dimmed text; staff-only hints are gated on `isStaff`.

## Tests and checks

Co-locate `*.test.tsx` (Vitest + Testing Library, jsdom).

```bash
pnpm --dir frontend format        # oxfmt
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
```
