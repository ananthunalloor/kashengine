import {
  Alert,
  Anchor,
  Button,
  Grid,
  Group,
  RingProgress,
  SegmentedControl,
  Select,
  Stack,
  Tabs,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { useEffect, useMemo, useState } from "react";
import {
  LuCircleAlert,
  LuDatabase,
  LuListChecks,
  LuRadio,
  LuSearch,
  LuTriangleAlert,
} from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  DirectionBadge,
  EmptyState,
  FreshnessTag,
  InfoTip,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  Sparkline,
  StatusBadge,
  StrengthMeter,
  formatDate,
  formatInr,
  formatNumber,
  formatSigned,
} from "../components";
import type { Column, Tone } from "../components";
import { indices, marketStatus } from "../mock/data";
import {
  instruments,
  instrumentsImportedAt,
  predictions,
  quotes,
  trackRecord,
} from "../mock/markets";
import type { Instrument, Prediction, PredictionResult, Quote } from "../mock/markets";

const ACCURACY_INFO =
  "Accuracy = predictions whose direction matched the index close ÷ all evaluated predictions. A day is evaluated after the 15:30 IST close: 'Rise' is right if the sample index closed above the previous close, 'Fall' if below, 'Flat' if within ±0.10%. Withheld calls and holidays are excluded. The baseline is how often simply guessing the most common direction would have been right over the same days.";

const resultMeta: Record<PredictionResult, { tone: Tone; label: string; glyph: string }> = {
  right: { tone: "gain", label: "Right", glyph: "✓" },
  wrong: { tone: "loss", label: "Wrong", glyph: "✕" },
  "no-session": { tone: "neutral", label: "No session", glyph: "–" },
  waiting: { tone: "caution", label: "Waiting", glyph: "…" },
};

/* ---------------------------------- Track record ---------------------------------- */

function HitStrip({ rows }: { rows: Prediction[] }) {
  const ordered = [...rows].reverse();
  const counts = rows.reduce<Record<PredictionResult, number>>(
    (acc, r) => ({ ...acc, [r.result]: acc[r.result] + 1 }),
    { right: 0, wrong: 0, "no-session": 0, waiting: 0 },
  );
  const evaluated = counts.right + counts.wrong;
  const colours: Record<PredictionResult, string> = {
    right: "var(--kv2-gain)",
    wrong: "var(--kv2-loss)",
    "no-session": "var(--kv2-neutral)",
    waiting: "var(--kv2-caution)",
  };
  return (
    <Panel
      title={`Last ${rows.length} sessions`}
      info="One square per trading day, oldest on the left. Green = direction call was right, red = wrong, amber = waiting for today's close, grey = no session (holiday) or withheld."
      actions={
        <StatusBadge tone="gain" size="xs">
          {evaluated ? ((counts.right / evaluated) * 100).toFixed(1) : "—"}% right
        </StatusBadge>
      }
    >
      <Stack gap={8}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${ordered.length}, minmax(0, 1fr))`,
            gap: 3,
          }}
          role="list"
          aria-label="Hit and miss by day"
        >
          {ordered.map((r) => (
            <Tooltip
              key={r.date}
              label={`${formatDate(r.date)} · ${resultMeta[r.result].label}`}
              withArrow
            >
              <span
                role="listitem"
                aria-label={`${formatDate(r.date)} ${resultMeta[r.result].label}`}
                style={{
                  aspectRatio: "1",
                  maxHeight: 28,
                  borderRadius: 3,
                  background: colours[r.result],
                  opacity: r.result === "no-session" ? 0.35 : 0.9,
                  color: "var(--kv2-surface)",
                  fontSize: 10,
                  display: "grid",
                  placeItems: "center",
                }}
              >
                {resultMeta[r.result].glyph}
              </span>
            </Tooltip>
          ))}
        </div>
        <Group justify="space-between" gap={8}>
          <Text size="xs" c="dimmed">
            {formatDate(ordered[0].date)}
          </Text>
          <Group gap={12}>
            {(Object.keys(counts) as PredictionResult[]).map((k) => (
              <Text key={k} size="xs" c="dimmed">
                {resultMeta[k].glyph} {resultMeta[k].label} ({counts[k]})
              </Text>
            ))}
          </Group>
          <Text size="xs" c="dimmed">
            {formatDate(ordered[ordered.length - 1].date)}
          </Text>
        </Group>
      </Stack>
    </Panel>
  );
}

const predictionColumns: Column<Prediction>[] = [
  {
    key: "day",
    header: "Day",
    sortValue: (r) => r.date,
    render: (r) => (
      <Group gap={6} wrap="nowrap">
        <Text size="sm" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          {formatDate(r.date)}
        </Text>
        {r.result === "waiting" ? (
          <StatusBadge tone="brand" size="xs">
            Today
          </StatusBadge>
        ) : null}
      </Group>
    ),
  },
  {
    key: "said",
    header: "We said",
    render: (r) =>
      r.said === "withheld" ? (
        <StatusBadge tone="neutral" size="xs">
          Withheld
        </StatusBadge>
      ) : (
        <DirectionBadge direction={r.said} size="xs" />
      ),
  },
  {
    key: "strength",
    header: "Strength",
    hideOnMobile: true,
    sortValue: (r) => r.strength,
    render: (r) => (r.said === "withheld" ? "—" : <StrengthMeter score={r.strength} />),
  },
  {
    key: "actual",
    header: "It was",
    render: (r) =>
      r.actual == null ? (
        <Text size="xs" c="dimmed">
          {r.result === "waiting" ? "After 15:30 IST" : "—"}
        </Text>
      ) : (
        <DirectionBadge direction={r.actual} size="xs" />
      ),
  },
  {
    key: "change",
    header: "Change",
    align: "right",
    sortValue: (r) => r.changePct ?? 0,
    render: (r) => (r.changePct == null ? "—" : <Delta value={r.changePct} />),
  },
  {
    key: "cue",
    header: "Top driving cue",
    hideOnMobile: true,
    render: (r) => (
      <Text size="xs" c="dimmed" lineClamp={1}>
        {r.cue}
      </Text>
    ),
  },
  {
    key: "result",
    header: "Result",
    sortValue: (r) => r.result,
    render: (r) => (
      <StatusBadge tone={resultMeta[r.result].tone} size="xs">
        {resultMeta[r.result].glyph} {resultMeta[r.result].label}
      </StatusBadge>
    ),
  },
];

function TrackRecordTab() {
  const [result, setResult] = useState("all");
  const [direction, setDirection] = useState<string | null>(null);
  const accuracy = (trackRecord.correct / trackRecord.total) * 100;
  const strong = (trackRecord.strongCorrect / trackRecord.strongTotal) * 100;
  const rows = useMemo(
    () =>
      predictions.filter(
        (p) => (result === "all" || p.result === result) && (!direction || p.said === direction),
      ),
    [result, direction],
  );

  return (
    <Stack gap={16}>
      {trackRecord.total < 30 ? (
        <Alert color="amber" variant="light" icon={<LuTriangleAlert size={16} />}>
          Fewer than 30 evaluated predictions — accuracy can swing a lot until more days are scored.
        </Alert>
      ) : null}
      <KpiGrid>
        <KpiTile
          label="Accuracy"
          info={ACCURACY_INFO}
          value={`${accuracy.toFixed(1)}%`}
          hint={`${trackRecord.correct} of ${trackRecord.total} days right`}
          delta={
            <Text size="xs" className="kv2-gain kv2-num" fw={500}>
              ▲ {formatSigned(accuracy - trackRecord.baseline, 1)} pts vs {trackRecord.baseline}%
              baseline
            </Text>
          }
          aside={
            <RingProgress
              size={44}
              thickness={5}
              roundCaps
              sections={[{ value: accuracy, color: "emerald.6" }]}
              label={
                <Text size="9px" ta="center" fw={600} className="kv2-num">
                  {Math.round(accuracy)}%
                </Text>
              }
            />
          }
        />
        <KpiTile
          label="Strong signals (≥ 7.0)"
          info="Only days where the call's strength was 7.0 / 10 or higher. Same right/wrong rule as overall accuracy."
          value={`${strong.toFixed(1)}%`}
          hint={`${trackRecord.strongCorrect} of ${trackRecord.strongTotal} right`}
        />
        <KpiTile
          label="Current streak"
          value={`${trackRecord.streak} days`}
          hint={`Last miss ${formatDate(trackRecord.lastMiss)}`}
        />
        <KpiTile
          label="Waiting for result"
          value={`${trackRecord.pending} session`}
          hint={`Settles ${trackRecord.nextSettlement}`}
          aside={
            <StatusBadge tone="caution" dot pulse size="xs">
              Pending
            </StatusBadge>
          }
        />
      </KpiGrid>

      <Grid gutter={16}>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <HitStrip rows={predictions} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Panel
            title="Last close"
            info="Saved end-of-day closes for the benchmark indices the model predicts against."
            flush
          >
            <Stack gap={0}>
              {indices.map((idx) => (
                <Group
                  key={idx.symbol}
                  justify="space-between"
                  wrap="nowrap"
                  px={12}
                  py={8}
                  style={{ borderBottom: "1px solid var(--kv2-border)" }}
                >
                  <Stack gap={0} style={{ minWidth: 0 }}>
                    <Text size="sm" fw={600}>
                      {idx.name}
                    </Text>
                    <Text size="xs" c="dimmed" className="kv2-mono">
                      {idx.symbol}
                    </Text>
                  </Stack>
                  <Stack gap={0} align="flex-end">
                    <Text size="sm" className="kv2-num" fw={600}>
                      {formatNumber(idx.last, 2)}
                    </Text>
                    <Delta value={idx.changePct} size="xs" />
                  </Stack>
                </Group>
              ))}
            </Stack>
          </Panel>
        </Grid.Col>
      </Grid>

      <Panel
        title="Predictions"
        info="The latest 30 daily direction calls for Sample Index 50 and how the index actually closed."
        flush
      >
        <DataTable
          columns={predictionColumns}
          rows={rows}
          rowKey={(r) => r.date}
          totalLabel="predictions"
          toolbar={
            <Group gap={8} wrap="wrap">
              <SegmentedControl
                aria-label="Result"
                value={result}
                onChange={setResult}
                data={[
                  { value: "all", label: "All" },
                  { value: "right", label: "Right" },
                  { value: "wrong", label: "Wrong" },
                  { value: "waiting", label: "Waiting" },
                ]}
              />
              <Select
                aria-label="Direction"
                placeholder="Direction: all"
                clearable
                value={direction}
                onChange={setDirection}
                w={170}
                data={[
                  { value: "up", label: "▲ Rise" },
                  { value: "down", label: "▼ Fall" },
                  { value: "flat", label: "– Flat" },
                  { value: "withheld", label: "Withheld" },
                ]}
              />
            </Group>
          }
          empty={
            <EmptyState
              title="No predictions match"
              description="Change the result or direction filter."
            />
          }
        />
      </Panel>
    </Stack>
  );
}

/* ---------------------------------- Live quotes ---------------------------------- */

const quoteColumns: Column<Quote>[] = [
  {
    key: "company",
    header: "Company",
    sortValue: (r) => r.name,
    render: (r) => (
      <Anchor component={AppLink} href={`/v2/companies/${r.id}/`} size="sm" fw={600}>
        {r.name}
      </Anchor>
    ),
  },
  {
    key: "symbol",
    header: "Symbol",
    hideOnMobile: true,
    render: (r) => (
      <Text size="xs" className="kv2-mono">
        {r.symbol}
      </Text>
    ),
  },
  {
    key: "price",
    header: "Price (INR)",
    align: "right",
    sortValue: (r) => r.price,
    render: (r) => (
      <Text size="sm" className="kv2-num" fw={600}>
        {formatInr(r.price)}
      </Text>
    ),
  },
  {
    key: "change",
    header: "Change %",
    align: "right",
    sortValue: (r) => r.changePct,
    render: (r) => <Delta value={r.changePct} />,
  },
  {
    key: "fresh",
    header: "Source & time",
    render: (r) =>
      r.fetchedAt == null ? (
        <Text size="xs" c="dimmed">
          Not fetched
        </Text>
      ) : (
        <FreshnessTag state={r.freshness} detail={r.fetchedAt} />
      ),
  },
  {
    key: "status",
    header: "Refresh",
    align: "center",
    hideOnMobile: true,
    render: (r) =>
      r.error ? (
        <Tooltip label={r.error} withArrow>
          <span aria-label={r.error} className="kv2-loss" style={{ display: "inline-flex" }}>
            <LuCircleAlert size={14} />
          </span>
        </Tooltip>
      ) : (
        <Tooltip label="No recorded error" withArrow>
          <span aria-label="No recorded error" className="kv2-gain">
            ✓
          </span>
        </Tooltip>
      ),
  },
];

function LiveQuotesTab() {
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return quotes.filter(
      (r) => !q || r.name.toLowerCase().includes(q) || r.symbol.toLowerCase().includes(q),
    );
  }, [query]);
  const stale = quotes.filter((q) => q.freshness === "stale").length;

  return (
    <Stack gap={16}>
      <KpiGrid>
        {indices.map((idx) => (
          <KpiTile
            key={idx.symbol}
            label={idx.name}
            value={<span className="kv2-num">{formatNumber(idx.last, 2)}</span>}
            delta={
              <Group gap={6}>
                <Delta value={idx.change} kind="points" size="xs" />
                <Delta value={idx.changePct} size="xs" />
              </Group>
            }
            hint={<FreshnessTag state="live" detail="11:42 IST" />}
            aside={<Sparkline data={idx.trend} w={72} h={24} />}
          />
        ))}
      </KpiGrid>
      {stale ? (
        <Alert color="amber" variant="light" icon={<LuTriangleAlert size={16} />}>
          {stale} quotes failed their last refresh and are showing older saved prices.
        </Alert>
      ) : null}
      <Panel
        title="Company quotes"
        info="Latest saved price observation per company. Live = updated within the last 60 seconds; Delayed = older than 60 seconds; Stale = last refresh failed. This page shows saved data and doesn't call the provider directly."
        actions={
          <FreshnessTag state={marketStatus.open ? "live" : "closed"} detail={marketStatus.asOf} />
        }
        flush
      >
        <DataTable
          columns={quoteColumns}
          rows={rows}
          rowKey={(r) => r.id}
          totalLabel="companies"
          toolbar={
            <TextInput
              leftSection={<LuSearch size={14} />}
              placeholder="Search company or symbol"
              aria-label="Search quotes"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              w={{ base: "100%", sm: 260 }}
            />
          }
          empty={
            <EmptyState title="No companies match" description="Try another name or symbol." />
          }
        />
      </Panel>
    </Stack>
  );
}

/* ---------------------------------- Instruments ---------------------------------- */

const instrumentColumns: Column<Instrument>[] = [
  {
    key: "symbol",
    header: "Symbol",
    sortValue: (r) => r.symbol,
    render: (r) => (
      <Stack gap={0}>
        <Text size="sm" fw={600} className="kv2-mono">
          {r.symbol}
        </Text>
        {r.companyId ? (
          <Anchor component={AppLink} href={`/v2/companies/${r.companyId}/`} size="xs">
            {r.name}
          </Anchor>
        ) : (
          <Text size="xs" c="dimmed">
            {r.name}
          </Text>
        )}
      </Stack>
    ),
  },
  {
    key: "exchange",
    header: "Exchange / segment",
    sortValue: (r) => `${r.exchange}${r.segment}`,
    render: (r) => (
      <Text size="sm" style={{ whiteSpace: "nowrap" }}>
        {r.exchange} · {r.segment}
      </Text>
    ),
  },
  {
    key: "type",
    header: "Type",
    sortValue: (r) => r.type,
    render: (r) => (
      <StatusBadge
        tone={r.type === "EQ" ? "brand" : r.type === "INDEX" ? "info" : "outline"}
        size="xs"
      >
        {r.type}
      </StatusBadge>
    ),
  },
  {
    key: "isin",
    header: "Underlying / ISIN",
    hideOnMobile: true,
    render: (r) => (
      <Text size="xs" className="kv2-mono">
        {r.isin ?? r.underlying ?? "—"}
      </Text>
    ),
  },
  {
    key: "expiry",
    header: "Expiry / strike",
    hideOnMobile: true,
    sortValue: (r) => r.expiry ?? "",
    render: (r) =>
      r.expiry ? (
        <Text size="xs" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          {formatDate(r.expiry)}
          {r.strike != null ? ` · ${formatNumber(r.strike)}` : ""}
        </Text>
      ) : null,
  },
  {
    key: "lot",
    header: "Lot size",
    align: "right",
    sortValue: (r) => r.lotSize,
    render: (r) => (
      <Text size="sm" className="kv2-num">
        {formatNumber(r.lotSize)}
      </Text>
    ),
  },
];

function InstrumentsTab() {
  const [query, setQuery] = useState("");
  const [exchange, setExchange] = useState("all");
  const [segment, setSegment] = useState<string | null>(null);
  const [type, setType] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return instruments.filter(
      (r) =>
        (exchange === "all" || r.exchange === exchange) &&
        (!segment || r.segment === segment) &&
        (!type || r.type === type) &&
        (!q ||
          r.symbol.toLowerCase().includes(q) ||
          r.name.toLowerCase().includes(q) ||
          (r.isin ?? "").toLowerCase().includes(q)),
    );
  }, [query, exchange, segment, type]);

  const filtered = query !== "" || exchange !== "all" || segment != null || type != null;
  const clear = () => {
    setQuery("");
    setExchange("all");
    setSegment(null);
    setType(null);
  };

  return (
    <Panel
      title="Instrument master"
      info="Reference list imported from the exchanges' daily instrument files. No prices here — use Live quotes or a company page for prices."
      actions={
        <Text size="xs" c="dimmed">
          Imported {instrumentsImportedAt}
        </Text>
      }
      flush
    >
      <DataTable
        columns={instrumentColumns}
        rows={rows}
        rowKey={(r) => r.key}
        pageSize={25}
        totalLabel="instruments"
        toolbar={
          <Group gap={8} wrap="wrap" style={{ width: "100%" }}>
            <TextInput
              leftSection={<LuSearch size={14} />}
              placeholder="Symbol, name or ISIN"
              aria-label="Search instruments"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              w={{ base: "100%", sm: 240 }}
            />
            <SegmentedControl
              aria-label="Exchange"
              value={exchange}
              onChange={setExchange}
              data={[
                { value: "all", label: "All" },
                { value: "NSE", label: "NSE" },
                { value: "BSE", label: "BSE" },
              ]}
            />
            <Select
              aria-label="Segment"
              placeholder="All segments"
              clearable
              value={segment}
              onChange={setSegment}
              w={150}
              data={["Equity", "F&O", "Index"]}
            />
            <Select
              aria-label="Instrument type"
              placeholder="All types"
              clearable
              value={type}
              onChange={setType}
              w={130}
              data={["EQ", "FUT", "CE", "PE", "INDEX"]}
            />
            <Text size="xs" c="dimmed" className="kv2-num">
              {formatNumber(rows.length)} results
            </Text>
            {filtered ? (
              <Anchor component="button" type="button" size="xs" onClick={clear}>
                Clear
              </Anchor>
            ) : null}
          </Group>
        }
        empty={
          <EmptyState
            title="No instruments match"
            description="Check the spelling or clear the exchange, segment and type filters."
          />
        }
      />
    </Panel>
  );
}

/* ---------------------------------- Page ---------------------------------- */

export function MarketsPage({ initialTab = "track" }: { initialTab?: string }) {
  const [tab, setTab] = useState<string | null>(initialTab);
  useEffect(() => setTab(initialTab), [initialTab]);
  return (
    <Page>
      <PageHeader
        title="Markets"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "Markets" }]}
        description="How well the daily direction calls have held up, the latest saved quotes, and the instrument reference list. All figures are sample data."
        meta={
          <Group gap={4}>
            <FreshnessTag
              state={marketStatus.open ? "live" : "closed"}
              detail={marketStatus.detail}
            />
            <InfoTip>{ACCURACY_INFO}</InfoTip>
          </Group>
        }
        actions={
          <Button
            variant="default"
            leftSection={<LuDatabase size={14} />}
            onClick={() => setTab("instruments")}
          >
            NSE & BSE instruments
          </Button>
        }
      />
      <Tabs value={tab} onChange={setTab} keepMounted={false}>
        <Tabs.List mb={16}>
          <Tabs.Tab value="track" leftSection={<LuListChecks size={14} />}>
            Track record
          </Tabs.Tab>
          <Tabs.Tab value="live" leftSection={<LuRadio size={14} />}>
            Live quotes
          </Tabs.Tab>
          <Tabs.Tab value="instruments" leftSection={<LuDatabase size={14} />}>
            Instruments
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="track">
          <TrackRecordTab />
        </Tabs.Panel>
        <Tabs.Panel value="live">
          <LiveQuotesTab />
        </Tabs.Panel>
        <Tabs.Panel value="instruments">
          <InstrumentsTab />
        </Tabs.Panel>
      </Tabs>
    </Page>
  );
}
