# Frontend UI Standard

React UI uses Mantine through `src/app/ThemeProvider.tsx`. Keep shared visual decisions in `src/app/uiStandard.ts` and the matching CSS custom properties in `src/styles/app.css`; do not introduce one-off global overrides for individual screens.

## Layout and spacing

- Use Mantine layout components (`Stack`, `Group`, `SimpleGrid`, and `Grid`) rather than custom flex or grid markup for routine layouts.
- Use the shared spacing scale from `src/app/uiStandard.ts`: `xs` for tight control internals, `sm` for related inline items, `md` for component internals, `lg` for related sections, `xl` for page-level separation, and `xxl` for major breaks.
- Use `Paper` and `Card` defaults for surfaces. Override spacing only when the content hierarchy needs a deliberate exception.
- For custom CSS, use the matching `--ui-*` variables in `src/styles/app.css` instead of introducing new spacing, radius, or control-size literals.
- All corners are square. Radius tokens are zero, and shared brand styles enforce this for library controls and pseudo-elements too; do not introduce rounded exceptions.
- Use the shared `AppFooter` outside the main landmark on public and authenticated React pages. Keep resource and legal links available without adding feature-gated navigation.

## Controls and icons

- Use Mantine buttons and form components so the shared size, padding, gap, and radius defaults apply. Avoid custom dimensions unless the control has a clear compact or prominent role.
- Use `@mantine/dates` for calendars and date entry, with its layered stylesheet after Mantine core. Date fields must submit ISO `YYYY-MM-DD` values and preserve required, disabled, validation, and date-bound behavior. Keep popover transitions disabled to avoid CSP-blocked style injection.
- Use `ActionIcon` for icon-only actions, with an accessible label or tooltip. Use the shared icon sizes from `uiStandard.controls.icon`; do not add global sizing rules to `svg`, because charts and illustrations need independent dimensions.
- Keep icons aligned with labels using Mantine's `leftSection` and `rightSection` props.
- Keep icon buttons square and sized consistently; do not apply icon dimensions to every SVG because charts and illustrations have their own geometry.

## Typography

- Use Mantine `Title` for headings and `Text` for body, secondary, and label content. Keep heading order semantic and use existing theme sizes rather than local font rules.
- Use `dimmed` for secondary copy and avoid one-off font families, weights, or letter spacing. Keep tracking at zero and use fixed type sizes with breakpoint adjustments rather than viewport-scaled font sizes.

## Exceptions

Explicit component props and local styles are appropriate for charts, dense data views, and other intentional hierarchy or visualization needs. Keep exceptions local, and prefer the shared CSS variables over literal spacing, radius, and control dimensions.
