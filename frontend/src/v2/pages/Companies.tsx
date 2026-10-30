import {
  Anchor,
  Button,
  Group,
  Menu,
  MultiSelect,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useRouter } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { LuDownload, LuEllipsis, LuRefreshCw, LuSearch, LuX } from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  EmptyState,
  InfoTip,
  Page,
  PageHeader,
  Panel,
  Sparkline,
  StatusBadge,
  SymbolChip,
  formatCompactInr,
  formatInr,
  formatNumber,
} from "../components";
import type { Column, Tone } from "../components";
import type { Company } from "../mock/data";
import { companies } from "../mock/data";
import { indexOf, indexOptions, sectorOptions } from "../mock/companies";

const signalTone: Record<Company["signal"], Tone> = {
  Accumulation: "gain",
  Distribution: "loss",
  Neutral: "neutral",
};
const signalGlyph: Record<Company["signal"], string> = {
  Accumulation: "▲",
  Distribution: "▼",
  Neutral: "–",
};

const columns: Column<Company>[] = [
  {
    key: "company",
    header: "Company",
    sortValue: (c) => c.name,
    render: (c) => (
      <Stack gap={2} style={{ minWidth: 160 }}>
        <Anchor
          component={AppLink}
          href={`/v2/companies/${c.id}/`}
          fw={600}
          size="sm"
          onClick={(e) => e.stopPropagation()}
        >
          {c.name}
        </Anchor>
        <Group gap={4}>
          <SymbolChip symbol={c.symbol} />
        </Group>
      </Stack>
    ),
  },
  {
    key: "sector",
    header: "Sector",
    sortValue: (c) => c.sector,
    render: (c) => c.sector,
    hideOnMobile: true,
  },
  {
    key: "ltp",
    header: "LTP",
    align: "right",
    sortValue: (c) => c.last,
    render: (c) => <span className="kv2-num">{formatInr(c.last)}</span>,
  },
  {
    key: "change",
    header: "1D change",
    align: "right",
    sortValue: (c) => c.changePct,
    render: (c) => <Delta value={c.changePct} />,
  },
  {
    key: "trend",
    header: "Trend",
    render: (c) => <Sparkline data={c.trend} w={88} h={24} />,
    hideOnMobile: true,
  },
  {
    key: "mcap",
    header: "Market cap",
    align: "right",
    sortValue: (c) => c.marketCap,
    render: (c) => <span className="kv2-num">{formatCompactInr(c.marketCap)}</span>,
  },
  {
    key: "pe",
    header: "P/E",
    align: "right",
    sortValue: (c) => c.pe,
    render: (c) => <span className="kv2-num">{formatNumber(c.pe, 1)}×</span>,
    hideOnMobile: true,
  },
  {
    key: "delivery",
    header: "Delivery %",
    align: "right",
    sortValue: (c) => c.deliveryPct,
    render: (c) => <span className="kv2-num">{formatNumber(c.deliveryPct, 1)}%</span>,
    hideOnMobile: true,
  },
  {
    key: "signal",
    header: "Signal",
    sortValue: (c) => c.signal,
    render: (c) => (
      <StatusBadge tone={signalTone[c.signal]} size="xs">
        {signalGlyph[c.signal]} {c.signal}
      </StatusBadge>
    ),
  },
];

export function CompaniesPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState("all");
  const [sectors, setSectors] = useState<string[]>([]);
  const [signal, setSignal] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return companies.filter(
      (c) =>
        (index === "all" || indexOf(c) === index) &&
        (sectors.length === 0 || sectors.includes(c.sector)) &&
        (!signal || c.signal === signal) &&
        (!q || `${c.name} ${c.symbol} ${c.sector}`.toLowerCase().includes(q)),
    );
  }, [query, index, sectors, signal]);

  const filtered = query !== "" || index !== "all" || sectors.length > 0 || signal !== null;
  const clear = () => {
    setQuery("");
    setIndex("all");
    setSectors([]);
    setSignal(null);
  };

  return (
    <Page>
      <PageHeader
        title="Companies"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "Companies" }]}
        description="Browse the sample company directory. Search by name, symbol or sector, and open a company for its chart, financials and news."
        meta={<StatusBadge tone="neutral">{formatNumber(companies.length)} listed</StatusBadge>}
        actions={
          <>
            <Button
              variant="default"
              leftSection={<LuDownload size={14} />}
              onClick={() =>
                notifications.show({
                  title: "Export started",
                  message: "Sample CSV export (mock only).",
                })
              }
            >
              Export CSV
            </Button>
            <Menu position="bottom-end">
              <Menu.Target>
                <Button variant="default" px={8} aria-label="More actions">
                  <LuEllipsis size={16} />
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Staff</Menu.Label>
                <Menu.Item
                  leftSection={<LuRefreshCw size={14} />}
                  onClick={() =>
                    notifications.show({
                      title: "Company list updated",
                      message: "24 sample companies checked · 0 added · 0 removed.",
                      color: "emerald",
                    })
                  }
                >
                  Update company list
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </>
        }
      />

      <Stack gap={12}>
        <Group gap={8} wrap="nowrap">
          <div style={{ overflowX: "auto", maxWidth: "100%" }}>
            <SegmentedControl
              value={index}
              onChange={setIndex}
              data={indexOptions.map((o) => ({ value: o.value, label: `${o.label} · ${o.count}` }))}
            />
          </div>
          <InfoTip>
            Index membership decides which companies are shown. The indices and their constituents
            here are fictional sample data.
          </InfoTip>
        </Group>

        <Panel flush>
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(c) => c.id}
            onRowClick={(c) => router.history.push(`/v2/companies/${c.id}/`)}
            totalLabel="companies"
            toolbar={
              <Group gap={8} wrap="wrap" w="100%">
                <TextInput
                  placeholder="Search name, symbol or sector"
                  aria-label="Search companies"
                  leftSection={<LuSearch size={14} />}
                  value={query}
                  onChange={(e) => setQuery(e.currentTarget.value)}
                  w={{ base: "100%", sm: 260 }}
                />
                <MultiSelect
                  placeholder={sectors.length ? undefined : "All sectors"}
                  aria-label="Sector"
                  data={sectorOptions}
                  value={sectors}
                  onChange={setSectors}
                  clearable
                  w={{ base: "100%", sm: 240 }}
                />
                <Select
                  placeholder="Any signal"
                  aria-label="Signal"
                  data={["Accumulation", "Neutral", "Distribution"]}
                  value={signal}
                  onChange={setSignal}
                  clearable
                  w={{ base: "100%", sm: 170 }}
                />
                <InfoTip>
                  Signal is a sample delivery-volume read: Accumulation means high delivery % on up
                  days, Distribution means high delivery % on down days.
                </InfoTip>
                {filtered ? (
                  <Button variant="subtle" leftSection={<LuX size={14} />} onClick={clear}>
                    Clear
                  </Button>
                ) : null}
                <Text size="xs" c="dimmed" ml="auto" className="kv2-num">
                  {formatNumber(rows.length)} of {formatNumber(companies.length)} companies
                </Text>
              </Group>
            }
            empty={
              <EmptyState
                title="No companies match"
                description="Try a different search, or clear the sector and signal filters."
                action={
                  <Button variant="default" onClick={clear}>
                    Clear filters
                  </Button>
                }
              />
            }
          />
        </Panel>
      </Stack>
    </Page>
  );
}
