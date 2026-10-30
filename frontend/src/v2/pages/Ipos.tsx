import {
  Anchor,
  Group,
  Select,
  SegmentedControl,
  Stack,
  Tabs,
  Text,
  TextInput,
} from "@mantine/core";
import { useRouter } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { LuSearch } from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  EmptyState,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  ScoreBar,
  StatusBadge,
  formatCompactInr,
  formatDate,
  formatInr,
  formatNumber,
  formatSigned,
} from "../components";
import type { Column, Tone } from "../components";
import { ipoStats, ipos, listingGainPct, statusLabel, verdictLabel } from "../mock/ipos";
import type { Ipo, IpoStatus, IpoVerdict } from "../mock/ipos";

const statusTone: Record<IpoStatus, Tone> = {
  open: "gain",
  upcoming: "info",
  closed: "caution",
  listed: "neutral",
};

const verdictTone: Record<IpoVerdict, Tone> = {
  positive: "gain",
  neutral: "neutral",
  avoid: "loss",
};

function shortDate(iso: string) {
  return formatDate(iso).slice(0, 6);
}

const columns: Column<Ipo>[] = [
  {
    key: "issue",
    header: "Issue",
    sortValue: (r) => r.name,
    render: (r) => (
      <Stack gap={0} style={{ minWidth: 160 }}>
        <Anchor
          component={AppLink}
          href={`/v2/ipos/${r.id}/`}
          fw={600}
          size="sm"
          onClick={(e) => e.stopPropagation()}
        >
          {r.name}
        </Anchor>
        <Text size="xs" c="dimmed" className="kv2-mono">
          {r.symbol} · {r.sector}
        </Text>
      </Stack>
    ),
  },
  {
    key: "board",
    header: "Board",
    hideOnMobile: true,
    render: (r) => (
      <StatusBadge tone={r.board === "SME" ? "caution" : "outline"} size="xs">
        {r.board}
      </StatusBadge>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (r) => (
      <StatusBadge tone={statusTone[r.status]} dot pulse={r.status === "open"} size="xs">
        {statusLabel[r.status]}
      </StatusBadge>
    ),
  },
  {
    key: "dates",
    header: "Dates",
    sortValue: (r) => r.openDate,
    render: (r) => (
      <Stack gap={0}>
        <Text size="sm" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          {shortDate(r.openDate)} – {formatDate(r.closeDate)}
        </Text>
        <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
          Lists {formatDate(r.listingDate)}
        </Text>
      </Stack>
    ),
  },
  {
    key: "price",
    header: "Price band",
    align: "right",
    sortValue: (r) => r.priceHigh,
    render: (r) => (
      <Stack gap={0} align="flex-end">
        <Text size="sm" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          {formatInr(r.priceLow, { decimals: 0 })} – {formatInr(r.priceHigh, { decimals: 0 })}
        </Text>
        <Text size="xs" c="dimmed" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          Lot {r.lotSize} · {formatInr(r.lotSize * r.priceHigh, { decimals: 0 })}
        </Text>
      </Stack>
    ),
  },
  {
    key: "size",
    header: "Issue size",
    align: "right",
    hideOnMobile: true,
    sortValue: (r) => r.issueSize,
    render: (r) => (
      <Text size="sm" className="kv2-num" style={{ whiteSpace: "nowrap" }}>
        {formatCompactInr(r.issueSize)}
      </Text>
    ),
  },
  {
    key: "sub",
    header: "Subscribed",
    align: "right",
    sortValue: (r) => r.subscription ?? -1,
    render: (r) =>
      r.subscription == null ? (
        <Text size="xs" c="dimmed">
          Not open
        </Text>
      ) : (
        <Text size="sm" fw={600} className="kv2-num">
          {formatNumber(r.subscription, 2)}x
        </Text>
      ),
  },
  {
    key: "gmp",
    header: "GMP",
    align: "right",
    hideOnMobile: true,
    sortValue: (r) => r.gmp ?? -1e9,
    render: (r) =>
      r.gmp == null ? (
        <Text size="xs" c="dimmed">
          No quotes
        </Text>
      ) : (
        <Stack gap={0} align="flex-end">
          <Text size="sm" className="kv2-num">
            ₹{formatSigned(r.gmp, 0)}
          </Text>
          <Delta value={(r.gmp / r.priceHigh) * 100} size="xs" decimals={1} />
        </Stack>
      ),
  },
  {
    key: "gain",
    header: "Listing gain",
    align: "right",
    sortValue: (r) => listingGainPct(r) ?? -1e9,
    render: (r) => {
      const gain = listingGainPct(r);
      return gain == null ? (
        <Text size="xs" c="dimmed">
          —
        </Text>
      ) : (
        <Stack gap={0} align="flex-end">
          <Delta value={gain} decimals={1} />
          <Text size="xs" c="dimmed">
            {r.listedAt != null ? "Actual" : "Estimated"}
          </Text>
        </Stack>
      );
    },
  },
  {
    key: "verdict",
    header: "Verdict",
    sortValue: (r) => r.score,
    render: (r) => (
      <StatusBadge tone={verdictTone[r.verdict]} size="xs">
        {verdictLabel[r.verdict]}
      </StatusBadge>
    ),
  },
  {
    key: "score",
    header: "Score",
    hideOnMobile: true,
    sortValue: (r) => r.score,
    render: (r) => (
      <Group gap={6} wrap="nowrap">
        <ScoreBar score={r.score} width={64} />
        <Text size="xs" className="kv2-num">
          {formatSigned(r.score)}
        </Text>
      </Group>
    ),
  },
];

type Tab = IpoStatus | "all";
const tabs: Tab[] = ["open", "upcoming", "closed", "listed", "all"];

export function MockIposPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("open");
  const [board, setBoard] = useState("all");
  const [verdict, setVerdict] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const counts = useMemo(() => {
    const c: Record<Tab, number> = { all: ipos.length, open: 0, upcoming: 0, listed: 0, closed: 0 };
    for (const ipo of ipos) c[ipo.status] += 1;
    return c;
  }, []);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return ipos.filter(
      (ipo) =>
        (tab === "all" || ipo.status === tab) &&
        (board === "all" || ipo.board === board) &&
        (!verdict || ipo.verdict === verdict) &&
        (!q || ipo.name.toLowerCase().includes(q) || ipo.symbol.toLowerCase().includes(q)),
    );
  }, [tab, board, verdict, query]);

  const filtered = board !== "all" || verdict != null || query !== "";
  const clear = () => {
    setBoard("all");
    setVerdict(null);
    setQuery("");
  };

  const upcomingSize = ipos
    .filter((i) => i.status === "upcoming")
    .reduce((sum, i) => sum + i.issueSize, 0);

  return (
    <Page>
      <PageHeader
        title="IPOs"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "IPOs" }]}
        description="Compare open and upcoming issues with the engine's verdict. Verdicts combine subscription demand, grey market premium (GMP), valuation against peers, financial trend and lead-manager record. GMP is unofficial and indicative only."
      />
      <Stack gap={16}>
        <KpiGrid>
          <KpiTile
            label="Open now"
            value={counts.open}
            hint="issues accepting bids"
            aside={
              <StatusBadge tone="gain" dot pulse size="xs">
                Bidding
              </StatusBadge>
            }
          />
          <KpiTile
            label="Upcoming"
            value={counts.upcoming}
            hint={`${formatCompactInr(upcomingSize)} combined issue size`}
          />
          <KpiTile
            label="Avg listing gain (2026)"
            value={<Delta value={ipoStats.avgListingGain} decimals={1} size="md" fw={600} />}
            hint={`Median ${formatSigned(ipoStats.medianListingGain, 1)}%`}
            info="Average first-day close versus the upper end of the price band, across all sample issues listed this year."
          />
          <KpiTile
            label="Verdict accuracy"
            value={`${ipoStats.verdictAccuracy}%`}
            hint={`${ipoStats.verdictHits} of ${ipoStats.verdictTotal} calls right`}
            info="A verdict counts as right when 'Likely to do well' listed above the issue price, 'Avoid' listed below it, or 'Neutral' listed within ±5%."
          />
        </KpiGrid>

        <Panel flush>
          <Tabs value={tab} onChange={(v) => setTab((v as Tab | null) ?? "open")}>
            <Tabs.List px={12} style={{ overflowX: "auto", flexWrap: "nowrap" }}>
              {tabs.map((t) => (
                <Tabs.Tab key={t} value={t}>
                  <Group gap={6} wrap="nowrap">
                    {t === "all" ? "All" : statusLabel[t]}
                    <StatusBadge tone={t === tab ? "brand" : "neutral"} size="xs">
                      {counts[t]}
                    </StatusBadge>
                  </Group>
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs>
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            onRowClick={(r) => router.history.push(`/v2/ipos/${r.id}/`)}
            totalLabel="issues"
            toolbar={
              <Group gap={8} wrap="wrap" style={{ width: "100%" }}>
                <TextInput
                  leftSection={<LuSearch size={14} />}
                  placeholder="Search issue or symbol"
                  aria-label="Search IPOs"
                  value={query}
                  onChange={(e) => setQuery(e.currentTarget.value)}
                  w={{ base: "100%", sm: 240 }}
                />
                <SegmentedControl
                  aria-label="Board"
                  value={board}
                  onChange={setBoard}
                  data={[
                    { value: "all", label: "All boards" },
                    { value: "Mainboard", label: "Mainboard" },
                    { value: "SME", label: "SME" },
                  ]}
                />
                <Select
                  aria-label="Verdict"
                  placeholder="All verdicts"
                  clearable
                  value={verdict}
                  onChange={setVerdict}
                  w={180}
                  data={(Object.keys(verdictLabel) as IpoVerdict[]).map((v) => ({
                    value: v,
                    label: verdictLabel[v],
                  }))}
                />
                {filtered ? (
                  <Anchor component="button" type="button" size="xs" onClick={clear}>
                    Clear filters
                  </Anchor>
                ) : null}
              </Group>
            }
            empty={
              <EmptyState
                title="No issues match"
                description="Try another status tab or clear the board, verdict and search filters."
                action={
                  filtered ? (
                    <Anchor component="button" type="button" size="xs" onClick={clear}>
                      Clear filters
                    </Anchor>
                  ) : undefined
                }
              />
            }
          />
        </Panel>
        <Text size="xs" c="dimmed">
          Sample data. Listing gain is estimated from GMP until the issue lists, then shows the
          actual first-day change. Not investment advice.
        </Text>
      </Stack>
    </Page>
  );
}

export { IposPage } from "./DataDriven";
