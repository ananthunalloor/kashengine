import {
  Box,
  Button,
  Checkbox,
  Grid,
  Group,
  HoverCard,
  Select,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  LuCheck,
  LuDownload,
  LuInfo,
  LuPlay,
  LuSearch,
  LuTriangleAlert,
  LuX,
} from "react-icons/lu";

import {
  CandlestickChart,
  Delta,
  DescriptionList,
  DirectionBadge,
  EmptyState,
  ErrorState,
  FreshnessTag,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  ScoreBar,
  SentimentPill,
  SkeletonRows,
  Sparkline,
  StatusBadge,
  StrengthMeter,
  SymbolChip,
  DataTable,
  formatCompactInr,
  formatInr,
  formatNumber,
} from "../components";
import type { Column, Tone } from "../components";
import { companies } from "../mock/data";
import type { Company } from "../mock/data";
import { mockCandles, mockSeries } from "../mock/generate";

const sections = [
  { id: "ds-colours", label: "Colours" },
  { id: "ds-type", label: "Typography" },
  { id: "ds-spacing", label: "Spacing & radius" },
  { id: "ds-status", label: "Status" },
  { id: "ds-forms", label: "Forms" },
  { id: "ds-table", label: "Data table" },
  { id: "ds-overlays", label: "Overlays" },
  { id: "ds-charts", label: "Charts" },
] as const;

const paletteNames = ["indigo", "slate", "emerald", "red", "amber", "sky"] as const;

const semanticVars: Array<[string, string]> = [
  ["canvas", "Page background"],
  ["surface", "Panels, cards, inputs"],
  ["surface-muted", "Table headers, toolbars"],
  ["border", "Hairline borders"],
  ["text", "Primary text"],
  ["text-muted", "Secondary text, labels"],
  ["brand", "Primary actions, links"],
  ["brand-soft", "Selected rows, active nav"],
  ["gain", "Rise ▲, success"],
  ["gain-soft", "Gain badge fill"],
  ["loss", "Fall ▼, failures"],
  ["loss-soft", "Loss badge fill"],
  ["caution", "Stale, pending, warnings"],
  ["caution-soft", "Caution badge fill"],
  ["info", "Informational, running"],
  ["info-soft", "Info badge fill"],
  ["neutral", "Flat –, disabled"],
];

const typeScale: Array<{ label: string; spec: string; use: string; node: ReactNode }> = [
  {
    label: "Page title",
    spec: "20 / 28 · 600",
    use: "One per page",
    node: <h1 className="kv2-page-title">Today</h1>,
  },
  {
    label: "Section",
    spec: "16 / 24 · 600",
    use: "Panel groups, modals",
    node: (
      <Text fz={16} fw={600}>
        Stocks to watch
      </Text>
    ),
  },
  {
    label: "Panel title",
    spec: "14 / 20 · 600",
    use: "Panel headers",
    node: <h2 className="kv2-panel-title">Market breadth</h2>,
  },
  {
    label: "Body",
    spec: "13 / 18 · 400",
    use: "Default text, table cells",
    node: <Text size="sm">Sample Index 50 is likely to rise.</Text>,
  },
  {
    label: "Small",
    spec: "11 / 14 · 400",
    use: "Hints, timestamps",
    node: (
      <Text size="xs" c="dimmed">
        Updated 11:42 IST
      </Text>
    ),
  },
  {
    label: "Eyebrow",
    spec: "11 · 600 · caps",
    use: "Metric labels",
    node: <span className="kv2-eyebrow">Signal strength</span>,
  },
  {
    label: "Numbers",
    spec: "tabular · kv2-num",
    use: "Prices, counts",
    node: (
      <Text size="sm" className="kv2-num">
        {formatInr(123456.78)}
      </Text>
    ),
  },
  {
    label: "Mono",
    spec: "kv2-mono",
    use: "Symbols, IDs, code",
    node: (
      <Text size="sm" className="kv2-mono">
        SMPL · run_0042
      </Text>
    ),
  },
];

const spacingScale: Array<[string, number]> = [
  ["xs", 4],
  ["sm", 8],
  ["md", 12],
  ["lg", 16],
  ["xl", 24],
];
const radiusScale: Array<[string, number]> = [
  ["xs", 4],
  ["sm", 6],
  ["md", 8],
  ["lg", 12],
  ["xl", 16],
];

const tones: Tone[] = ["gain", "loss", "caution", "info", "brand", "neutral", "outline"];

export function DesignSystemPage() {
  const [active, setActive] = useState<string>(sections[0].id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-100px 0px -70% 0px" },
    );
    sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const jump = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <Page>
      <PageHeader
        title="Design system"
        crumbs={[{ label: "Gallery", to: "/v2/" }, { label: "Design system" }]}
        meta={<StatusBadge tone="brand">v2 · Mantine 8</StatusBadge>}
        description="Living reference of the v2 tokens and shared components. Everything here is rendered by the real components, so it stays in sync with the code."
        actions={
          <Button
            variant="default"
            leftSection={<LuDownload size={14} />}
            onClick={() =>
              notifications.show({
                title: "Tokens exported",
                message: "Sample tokens.json prepared (mock).",
              })
            }
          >
            Export tokens
          </Button>
        }
      />

      <Box
        component="nav"
        aria-label="Design system sections"
        style={{
          position: "sticky",
          top: 48,
          zIndex: 5,
          background: "var(--kv2-canvas)",
          borderBottom: "1px solid var(--kv2-border)",
          margin: "0 0 16px",
          padding: "6px 0",
          overflowX: "auto",
        }}
      >
        <Group gap={4} wrap="nowrap">
          {sections.map((s) => (
            <Button
              key={s.id}
              size="xs"
              variant={active === s.id ? "light" : "subtle"}
              color={active === s.id ? "indigo" : "slate"}
              onClick={() => jump(s.id)}
              style={{ flexShrink: 0 }}
            >
              {s.label}
            </Button>
          ))}
        </Group>
      </Box>

      <Stack gap={24}>
        <Section
          id="ds-colours"
          title="Colours"
          description="Theme palettes (shades 0–9) and the semantic --kv2-* variables. Use the semantic variables in components so light and dark mode both work."
        >
          <Panel
            title="Palette"
            info='Use as Mantine colours, e.g. color="indigo.6", or as var(--mantine-color-indigo-6).'
          >
            <Stack gap={8}>
              {paletteNames.map((name) => (
                <Group key={name} gap={8} wrap="nowrap">
                  <Text size="xs" w={64} className="kv2-mono">
                    {name}
                  </Text>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(10, minmax(0, 1fr))",
                      gap: 2,
                      flex: 1,
                    }}
                  >
                    {Array.from({ length: 10 }, (_, i) => (
                      <Tooltip key={i} label={`var(--mantine-color-${name}-${i})`}>
                        <div
                          style={{
                            height: 28,
                            borderRadius: 4,
                            background: `var(--mantine-color-${name}-${i})`,
                            border: "1px solid var(--kv2-border)",
                            display: "flex",
                            alignItems: "flex-end",
                            justifyContent: "center",
                            fontSize: 10,
                            color: i >= 5 ? "#fff" : "#0f172a",
                          }}
                        >
                          {i}
                        </div>
                      </Tooltip>
                    ))}
                  </div>
                </Group>
              ))}
            </Stack>
          </Panel>
          <Panel title="Semantic variables" info="Defined per colour scheme by the v2 theme scope.">
            <SimpleGrid cols={{ base: 1, xs: 2, md: 3, lg: 4 }} spacing={8}>
              {semanticVars.map(([name, use]) => (
                <Group key={name} gap={8} wrap="nowrap">
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      flexShrink: 0,
                      borderRadius: 4,
                      background: `var(--kv2-${name})`,
                      border: "1px solid var(--kv2-border)",
                    }}
                  />
                  <Stack gap={0} style={{ minWidth: 0 }}>
                    <Text size="xs" className="kv2-mono" truncate>
                      --kv2-{name}
                    </Text>
                    <Text size="xs" c="dimmed" truncate>
                      {use}
                    </Text>
                  </Stack>
                </Group>
              ))}
            </SimpleGrid>
          </Panel>
        </Section>

        <Section
          id="ds-type"
          title="Typography"
          description="Inter for text, JetBrains Mono for symbols and IDs. Numbers use tabular figures so columns line up."
        >
          <Panel flush>
            {typeScale.map((t, i) => (
              <Group
                key={t.label}
                justify="space-between"
                wrap="wrap"
                gap={8}
                px={12}
                py={10}
                style={i ? { borderTop: "1px solid var(--kv2-border)" } : undefined}
              >
                <Box style={{ flex: "1 1 240px", minWidth: 0 }}>{t.node}</Box>
                <Group gap={12} wrap="nowrap">
                  <Text size="xs" fw={600} w={90}>
                    {t.label}
                  </Text>
                  <Text size="xs" className="kv2-mono" c="dimmed" w={120}>
                    {t.spec}
                  </Text>
                  <Text size="xs" c="dimmed" w={150} visibleFrom="sm">
                    {t.use}
                  </Text>
                </Group>
              </Group>
            ))}
          </Panel>
        </Section>

        <Section
          id="ds-spacing"
          title="Spacing & radius"
          description="4px base grid. Compact controls (32px) and crisp small radii; resting surfaces have hairline borders and no shadow."
        >
          <SimpleGrid cols={{ base: 1, md: 3 }} spacing={16}>
            <Panel title="Spacing">
              <Stack gap={8}>
                {spacingScale.map(([k, v]) => (
                  <Group key={k} gap={8} wrap="nowrap">
                    <Text size="xs" className="kv2-mono" w={56}>
                      {k} · {v}
                    </Text>
                    <div
                      style={{
                        width: v * 4,
                        height: 12,
                        background: "var(--kv2-brand-soft)",
                        borderLeft: "2px solid var(--kv2-brand)",
                      }}
                    />
                  </Group>
                ))}
              </Stack>
            </Panel>
            <Panel title="Radius">
              <Group gap={12}>
                {radiusScale.map(([k, v]) => (
                  <Stack key={k} gap={4} align="center">
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: v,
                        border: "1px solid var(--kv2-border)",
                        background: "var(--kv2-surface-muted)",
                      }}
                    />
                    <Text size="xs" className="kv2-mono">
                      {k} · {v}
                    </Text>
                  </Stack>
                ))}
              </Group>
            </Panel>
            <Panel title="Layout invariants">
              <DescriptionList
                items={[
                  ["Control height", "32px (inputs, buttons, selects)"],
                  ["Table rows", "32–36px, 13px tabular figures"],
                  ["Default radius", "4px (xs)"],
                  ["Elevation", "Hairline border; shadow only on overlays"],
                  ["Shell", "48px header · collapsible sidebar"],
                  ["Page width", "max 1440px"],
                ]}
              />
            </Panel>
          </SimpleGrid>
        </Section>

        <Section
          id="ds-status"
          title="Status vocabulary"
          description="Colour is never the only signal: direction always carries ▲ ▼ – and statuses always carry text."
        >
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing={16}>
            <Panel title="StatusBadge tones">
              <Stack gap={8}>
                <Group gap={6}>
                  {tones.map((t) => (
                    <StatusBadge key={t} tone={t}>
                      {t}
                    </StatusBadge>
                  ))}
                </Group>
                <Group gap={6}>
                  <StatusBadge tone="gain" dot pulse>
                    Running
                  </StatusBadge>
                  <StatusBadge tone="caution" dot>
                    Pending
                  </StatusBadge>
                  <StatusBadge tone="loss" dot size="xs">
                    Failed
                  </StatusBadge>
                  <StatusBadge tone="info" size="xs" icon={<LuInfo size={11} />}>
                    With icon
                  </StatusBadge>
                </Group>
              </Stack>
            </Panel>
            <Panel title="Direction & sentiment">
              <Stack gap={8}>
                <Group gap={12}>
                  <Delta value={2.48} />
                  <Delta value={-1.82} />
                  <Delta value={0} />
                  <Delta value={142.3} kind="points" />
                </Group>
                <Group gap={6}>
                  <DirectionBadge direction="up" />
                  <DirectionBadge direction="down" />
                  <DirectionBadge direction="flat" />
                </Group>
                <Group gap={6}>
                  <SentimentPill score={0.64} />
                  <SentimentPill score={-0.42} />
                  <SentimentPill score={0.05} />
                </Group>
              </Stack>
            </Panel>
            <Panel
              title="Freshness & symbols"
              info="Freshness tells the user how old the data on screen is."
            >
              <Stack gap={8}>
                <Group gap={6}>
                  <FreshnessTag state="live" detail="12ms" />
                  <FreshnessTag state="delayed" detail="2m" />
                  <FreshnessTag state="stale" detail="since 10:05" />
                  <FreshnessTag state="closed" />
                </Group>
                <Group gap={6}>
                  <SymbolChip symbol="SMPL" />
                  <SymbolChip symbol="500000" exchange="BSE" />
                  <SymbolChip symbol={companies[0].symbol} />
                </Group>
              </Stack>
            </Panel>
            <Panel
              title="Scores"
              info="StrengthMeter shows a 0–10 score in 5 segments; ScoreBar shows a −1…+1 balance centred on zero."
            >
              <Stack gap={8}>
                <StrengthMeter score={7.8} tone="gain" />
                <StrengthMeter score={5.4} />
                <StrengthMeter score={2.1} tone="loss" />
                <Group gap={12}>
                  <ScoreBar score={0.64} />
                  <ScoreBar score={-0.4} />
                  <ScoreBar score={0.05} />
                </Group>
              </Stack>
            </Panel>
          </SimpleGrid>
          <KpiGrid cols={4}>
            <KpiTile
              label="KpiTile"
              value={formatInr(24311.2)}
              delta={<Delta value={0.59} size="xs" />}
              hint="vs prev close"
              info="Every key metric gets a short explanation."
            />
            <KpiTile
              label="With aside"
              value={formatNumber(1420)}
              hint="advancers"
              aside={<Sparkline data={mockSeries(24, 100, 5, 0.03)} w={56} h={20} />}
            />
            <KpiTile label="Market cap" value={formatCompactInr(1.24e12)} hint="compact INR" />
            <KpiTile
              label="Accuracy"
              value="68.9%"
              delta={<Delta value={14.5} kind="points" size="xs" decimals={1} />}
              hint="vs baseline"
            />
          </KpiGrid>
          <SimpleGrid cols={{ base: 1, md: 3 }} spacing={16}>
            <Panel title="EmptyState">
              <EmptyState
                title="No stories match"
                description="Try clearing the filters."
                action={
                  <Button size="xs" variant="default">
                    Clear filters
                  </Button>
                }
              />
            </Panel>
            <Panel title="ErrorState">
              <ErrorState
                description="The sample feed did not respond."
                onRetry={() => notifications.show({ message: "Retrying (mock)…" })}
              />
            </Panel>
            <Panel title="SkeletonRows" flush>
              <SkeletonRows rows={4} />
            </Panel>
          </SimpleGrid>
        </Section>

        <Section
          id="ds-forms"
          title="Form controls"
          description="Compact 32px controls. Labels above inputs; help text below."
        >
          <Panel>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing={16}>
              <TextInput
                label="Search"
                placeholder="Symbol or company"
                leftSection={<LuSearch size={14} />}
                description="Matches name or symbol"
              />
              <Select
                label="Exchange"
                defaultValue="nse"
                data={[
                  { value: "nse", label: "NSE equity" },
                  { value: "bse", label: "BSE equity" },
                  { value: "fo", label: "Sample derivatives" },
                ]}
              />
              <Stack gap={4}>
                <Text size="sm" fw={500}>
                  Interval
                </Text>
                <SegmentedControl data={["1D", "1W", "1M", "1Y"]} defaultValue="1M" />
              </Stack>
              <TextInput label="With error" defaultValue="abc" error="Enter a valid 6-digit code" />
            </SimpleGrid>
            <Group gap={24} mt={16} wrap="wrap">
              <Switch label="Email delivery" defaultChecked />
              <Switch label="Disabled" disabled />
              <Checkbox label="Include IPOs" defaultChecked />
              <Checkbox label="Indeterminate" indeterminate />
            </Group>
            <Group gap={8} mt={16} wrap="wrap">
              <Button leftSection={<LuPlay size={14} />}>Primary</Button>
              <Button variant="default">Default</Button>
              <Button variant="subtle">Subtle</Button>
              <Button variant="light">Light</Button>
              <Button color="red">Danger</Button>
              <Button loading>Loading</Button>
              <Button disabled>Disabled</Button>
              <Button size="xs" variant="default">
                Extra small
              </Button>
            </Group>
          </Panel>
        </Section>

        <Section
          id="ds-table"
          title="Data table"
          description="Toolbar filters apply immediately; headers sort; secondary columns hide on mobile and the table scrolls horizontally."
        >
          <TableDemo />
        </Section>

        <Section
          id="ds-overlays"
          title="Overlays"
          description="Confirm destructive actions in a modal; report results with a toast; reveal detail on hover."
        >
          <Panel>
            <Group gap={8} wrap="wrap">
              <Button
                color="red"
                variant="light"
                onClick={() =>
                  modals.openConfirmModal({
                    title: "Pause daily delivery?",
                    children: (
                      <Text size="sm">
                        Subscribers will stop receiving the sample brief until delivery is resumed.
                      </Text>
                    ),
                    labels: { confirm: "Pause delivery", cancel: "Cancel" },
                    confirmProps: { color: "red" },
                    onConfirm: () =>
                      notifications.show({
                        title: "Delivery paused",
                        message: "Sample action only.",
                        color: "amber",
                      }),
                  })
                }
              >
                Open confirm modal
              </Button>
              <Button
                variant="default"
                leftSection={<LuCheck size={14} />}
                onClick={() =>
                  notifications.show({
                    title: "Invite sent",
                    message: "Sample invite emailed to user@example.com.",
                    color: "emerald",
                  })
                }
              >
                Success toast
              </Button>
              <Button
                variant="default"
                leftSection={<LuX size={14} />}
                onClick={() =>
                  notifications.show({
                    title: "Delivery failed",
                    message: "Sample webhook returned 502. Retrying in 45s.",
                    color: "red",
                    autoClose: false,
                  })
                }
              >
                Error toast (persistent)
              </Button>
              <Button
                variant="default"
                leftSection={<LuTriangleAlert size={14} />}
                onClick={() =>
                  notifications.show({
                    title: "Feed delayed",
                    message: "Sample quotes are 2 minutes behind.",
                    color: "amber",
                  })
                }
              >
                Warning toast
              </Button>
              <HoverCard width={280} position="bottom-start" withArrow>
                <HoverCard.Target>
                  <UnstyledButton>
                    <StatusBadge tone="info" icon={<LuInfo size={12} />}>
                      Hover: VWAP
                    </StatusBadge>
                  </UnstyledButton>
                </HoverCard.Target>
                <HoverCard.Dropdown>
                  <Stack gap={4}>
                    <Text size="sm" fw={600}>
                      Volume-weighted average price
                    </Text>
                    <Text size="xs" c="dimmed">
                      Average traded price weighted by volume since the open. Prices above VWAP
                      suggest buyers are in control.
                    </Text>
                    <Group gap={4}>
                      <Text size="xs">Current deviation</Text>
                      <Delta value={0.42} size="xs" />
                    </Group>
                  </Stack>
                </HoverCard.Dropdown>
              </HoverCard>
              <Tooltip label="Tooltips hold one short sentence">
                <Button variant="subtle">Tooltip</Button>
              </Tooltip>
            </Group>
          </Panel>
        </Section>

        <Section
          id="ds-charts"
          title="Charts"
          description="Sparklines for inline trends; candlesticks for price history; Mantine charts for everything else."
        >
          <Grid gutter={16}>
            <Grid.Col span={{ base: 12, md: 4 }}>
              <Panel title="Sparkline">
                <Stack gap={12}>
                  <Group justify="space-between">
                    <Text size="sm">Rising</Text>
                    <Sparkline data={mockSeries(30, 100, 21, 0.08)} />
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">Falling</Text>
                    <Sparkline data={mockSeries(30, 100, 22, -0.08)} />
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">Full width</Text>
                  </Group>
                  <Sparkline data={mockSeries(60, 100, 23, 0.01)} w="100%" h={40} />
                </Stack>
              </Panel>
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 8 }}>
              <Panel
                title="CandlestickChart"
                info="Sample OHLC data with 20/50-day moving averages and volume."
              >
                <CandlestickChart
                  candles={mockCandles(90, 1000, 9)}
                  height={260}
                  overlays={["sma20", "sma50"]}
                  showVolume
                />
              </Panel>
            </Grid.Col>
          </Grid>
        </Section>
      </Stack>
    </Page>
  );
}

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Box component="section" id={id} style={{ scrollMarginTop: 100 }}>
      <Stack gap={4} mb={12}>
        <Text component="h2" fz={16} fw={600} m={0}>
          {title}
        </Text>
        <Text size="xs" c="dimmed">
          {description}
        </Text>
      </Stack>
      <Stack gap={16}>{children}</Stack>
    </Box>
  );
}

const signalTone: Record<Company["signal"], Tone> = {
  Accumulation: "gain",
  Distribution: "loss",
  Neutral: "neutral",
};

function TableDemo() {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [signal, setSignal] = useState("all");
  const sectors = useMemo(() => [...new Set(companies.map((c) => c.sector))].sort(), []);

  const rows = companies.filter(
    (c) =>
      (!query || `${c.name} ${c.symbol}`.toLowerCase().includes(query.toLowerCase())) &&
      (!sector || c.sector === sector) &&
      (signal === "all" || c.signal === signal),
  );

  const columns: Column<Company>[] = [
    {
      key: "name",
      header: "Company",
      sortValue: (r) => r.name,
      render: (r) => (
        <Stack gap={0}>
          <Text size="sm" fw={600}>
            {r.name}
          </Text>
          <Text size="xs" c="dimmed" className="kv2-mono">
            {r.symbol}
          </Text>
        </Stack>
      ),
    },
    {
      key: "sector",
      header: "Sector",
      hideOnMobile: true,
      sortValue: (r) => r.sector,
      render: (r) => r.sector,
    },
    {
      key: "last",
      header: "Last (₹)",
      align: "right",
      sortValue: (r) => r.last,
      render: (r) => <span className="kv2-num">{formatInr(r.last)}</span>,
    },
    {
      key: "chg",
      header: "Change",
      align: "right",
      sortValue: (r) => r.changePct,
      render: (r) => <Delta value={r.changePct} size="xs" />,
    },
    {
      key: "trend",
      header: "Trend",
      hideOnMobile: true,
      render: (r) => <Sparkline data={r.trend} w={64} h={20} />,
    },
    {
      key: "deliv",
      header: "Delivery %",
      align: "right",
      hideOnMobile: true,
      sortValue: (r) => r.deliveryPct,
      render: (r) => <span className="kv2-num">{r.deliveryPct}%</span>,
    },
    {
      key: "mcap",
      header: "Mkt cap",
      align: "right",
      hideOnMobile: true,
      sortValue: (r) => r.marketCap,
      render: (r) => <span className="kv2-num">{formatCompactInr(r.marketCap)}</span>,
    },
    {
      key: "signal",
      header: "Signal",
      sortValue: (r) => r.signal,
      render: (r) => (
        <StatusBadge tone={signalTone[r.signal]} size="xs">
          {r.signal}
        </StatusBadge>
      ),
    },
  ];

  const filtered = Boolean(query || sector || signal !== "all");

  return (
    <Panel flush>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        pageSize={5}
        totalLabel="companies"
        onRowClick={(r) => notifications.show({ message: `Would open ${r.name} (sample).` })}
        toolbar={
          <Group gap={8} wrap="wrap" style={{ flex: 1 }}>
            <TextInput
              placeholder="Search company or symbol"
              leftSection={<LuSearch size={14} />}
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              w={{ base: "100%", sm: 220 }}
            />
            <Select
              placeholder="All sectors"
              data={sectors}
              value={sector}
              onChange={setSector}
              clearable
              w={{ base: "100%", sm: 160 }}
            />
            <SegmentedControl
              value={signal}
              onChange={setSignal}
              data={[
                { value: "all", label: "All" },
                { value: "Accumulation", label: "Accum." },
                { value: "Distribution", label: "Distrib." },
              ]}
            />
            {filtered ? (
              <Button
                variant="subtle"
                size="xs"
                onClick={() => {
                  setQuery("");
                  setSector(null);
                  setSignal("all");
                }}
              >
                Clear
              </Button>
            ) : null}
            <Text size="xs" c="dimmed" ml="auto">
              {rows.length} of {companies.length} companies
            </Text>
          </Group>
        }
        empty={
          <EmptyState
            title="No companies match"
            description="Clear the filters to see all sample companies."
          />
        }
      />
    </Panel>
  );
}
