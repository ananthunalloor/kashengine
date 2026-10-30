import {
  Anchor,
  Button,
  Group,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  LuCalendarDays,
  LuChevronRight,
  LuDownload,
  LuRefreshCw,
  LuSearch,
  LuTable,
  LuX,
} from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  DirectionBadge,
  EmptyState,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  StatusBadge,
  StrengthMeter,
  formatDate,
} from "../components";
import type { Column, Tone } from "../components";
import { sampleUser } from "../mock/data";
import { outcomeOf, reports } from "../mock/reports";
import type { DailyReport, Outcome, Outlook } from "../mock/reports";

const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function monthLabel(key: string) {
  const [y, m] = key.split("-").map(Number);
  return `${months[m - 1]} ${y}`;
}

export function OutlookBadge({ outlook, size = "sm" }: { outlook: Outlook; size?: "xs" | "sm" }) {
  if (outlook === "na")
    return (
      <StatusBadge tone="neutral" size={size}>
        Not available
      </StatusBadge>
    );
  return <DirectionBadge direction={outlook} size={size} />;
}

const outcomeMeta: Record<Outcome, { tone: Tone; label: string }> = {
  hit: { tone: "gain", label: "Hit" },
  miss: { tone: "loss", label: "Miss" },
  pending: { tone: "caution", label: "Pending" },
  na: { tone: "neutral", label: "—" },
};

export function OutcomeBadge({ report }: { report: DailyReport }) {
  const { tone, label } = outcomeMeta[outcomeOf(report)];
  return (
    <StatusBadge tone={tone} size="xs">
      {label}
    </StatusBadge>
  );
}

function deliverySummary(report: DailyReport) {
  const sent = report.delivery.filter((d) => d.result === "sent").length;
  const total = report.delivery.length;
  if (total === 0)
    return (
      <StatusBadge tone="neutral" size="xs">
        Not sent
      </StatusBadge>
    );
  return (
    <StatusBadge tone={sent === total ? "gain" : "caution"} size="xs">
      {sent}/{total} sent
    </StatusBadge>
  );
}

const outlookTone: Record<Outlook, string> = {
  up: "var(--kv2-gain-soft)",
  down: "var(--kv2-loss-soft)",
  flat: "var(--kv2-surface-muted)",
  na: "transparent",
};

/** Month grid coloured by outlook; each trading day links to its report. */
function CalendarHeatmap({ month, rows }: { month: string; rows: DailyReport[] }) {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const offset = (first.getUTCDay() + 6) % 7;
  const byDay = new Map(rows.map((r) => [r.day, r]));
  const cells: Array<string | null> = [
    ...Array.from({ length: offset }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`),
  ];
  return (
    <Stack gap={8} p={12}>
      <SimpleGrid cols={7} spacing={4} verticalSpacing={4}>
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <Text key={d} className="kv2-eyebrow" ta="center">
            {d}
          </Text>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={`e${i}`} />;
          const report = byDay.get(day);
          const dayNum = Number(day.slice(8));
          if (!report)
            return (
              <div
                key={day}
                style={{
                  minHeight: 52,
                  borderRadius: 4,
                  border: "1px dashed var(--kv2-border)",
                  padding: 6,
                  color: "var(--kv2-text-muted)",
                  fontSize: 11,
                }}
              >
                {dayNum}
              </div>
            );
          const outcome = outcomeOf(report);
          return (
            <Tooltip
              key={day}
              label={`${formatDate(day)} · ${report.outlook === "na" ? "No outlook" : `${report.outlook.toUpperCase()} ${report.strength.toFixed(1)}/10`} · ${outcomeMeta[outcome].label}`}
            >
              <UnstyledButton
                component={AppLink}
                href={`/v2/reports/${day}/`}
                style={{
                  minHeight: 52,
                  borderRadius: 4,
                  border: "1px solid var(--kv2-border)",
                  background: outlookTone[report.outlook],
                  padding: 6,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <Group justify="space-between" gap={2} wrap="nowrap">
                  <Text fz={11} fw={600} className="kv2-num">
                    {dayNum}
                  </Text>
                  {outcome === "hit" || outcome === "miss" ? (
                    <Text fz={10} className={outcome === "hit" ? "kv2-gain" : "kv2-loss"} fw={700}>
                      {outcome === "hit" ? "✓" : "✗"}
                    </Text>
                  ) : null}
                </Group>
                <Text
                  fz={11}
                  fw={600}
                  className={
                    report.outlook === "up"
                      ? "kv2-gain"
                      : report.outlook === "down"
                        ? "kv2-loss"
                        : "kv2-flat"
                  }
                  visibleFrom="xs"
                >
                  {report.outlook === "up" ? "▲" : report.outlook === "down" ? "▼" : "–"}{" "}
                  {report.outlook === "na" ? "n/a" : report.strength.toFixed(1)}
                </Text>
              </UnstyledButton>
            </Tooltip>
          );
        })}
      </SimpleGrid>
      <Group gap={12}>
        <Text size="xs" c="dimmed">
          Legend:
        </Text>
        <StatusBadge tone="gain" size="xs">
          ▲ Rise
        </StatusBadge>
        <StatusBadge tone="loss" size="xs">
          ▼ Fall
        </StatusBadge>
        <StatusBadge tone="neutral" size="xs">
          – Flat / n/a
        </StatusBadge>
        <Text size="xs" c="dimmed">
          ✓ hit · ✗ miss · dashed = no session
        </Text>
      </Group>
    </Stack>
  );
}

export function MockReportsPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<"table" | "calendar">("table");
  const [search, setSearch] = useState("");
  const [outlook, setOutlook] = useState<string>("all");
  const [outcome, setOutcome] = useState<string | null>("all");
  const [month, setMonth] = useState<string | null>("all");

  const monthKeys = useMemo(() => [...new Set(reports.map((r) => r.day.slice(0, 7)))], []);
  const latest = reports[0];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return reports.filter((r) => {
      if (outlook !== "all" && r.outlook !== outlook) return false;
      if (outcome && outcome !== "all" && outcomeOf(r) !== outcome) return false;
      if (month && month !== "all" && !r.day.startsWith(month)) return false;
      if (q && !`${r.day} ${formatDate(r.day)} ${r.headline}`.toLowerCase().includes(q))
        return false;
      return true;
    });
  }, [search, outlook, outcome, month]);

  const settled = reports.slice(0, 63).filter((r) => ["hit", "miss"].includes(outcomeOf(r)));
  const hitRate =
    (settled.filter((r) => outcomeOf(r) === "hit").length / Math.max(1, settled.length)) * 100;
  const latestMonth = latest.day.slice(0, 7);
  const monthRows = reports.filter((r) => r.day.startsWith(latestMonth));
  const latestSent = latest.delivery.filter((d) => d.result === "sent").length;
  const filtersActive = search !== "" || outlook !== "all" || outcome !== "all" || month !== "all";
  const calendarMonth = month && month !== "all" ? month : latestMonth;

  const clear = () => {
    setSearch("");
    setOutlook("all");
    setOutcome("all");
    setMonth("all");
  };

  const columns: Column<DailyReport>[] = [
    {
      key: "day",
      header: "Report date",
      sortValue: (r) => r.day,
      render: (r) => (
        <Anchor
          component={AppLink}
          href={`/v2/reports/${r.day}/`}
          fw={600}
          size="sm"
          className="kv2-num"
          onClick={(e) => e.stopPropagation()}
          style={{ whiteSpace: "nowrap" }}
        >
          {formatDate(r.day)}
        </Anchor>
      ),
    },
    {
      key: "outlook",
      header: "Outlook",
      render: (r) => <OutlookBadge outlook={r.outlook} size="xs" />,
    },
    {
      key: "strength",
      header: "Strength",
      sortValue: (r) => r.strength,
      render: (r) =>
        r.outlook === "na" ? (
          <Text size="xs" c="dimmed">
            —
          </Text>
        ) : (
          <StrengthMeter score={r.strength} />
        ),
    },
    {
      key: "actual",
      header: "Actual (index)",
      align: "right",
      sortValue: (r) => r.actualPct ?? 0,
      render: (r) =>
        r.actualPct == null ? (
          <Text size="xs" c="dimmed">
            Session open
          </Text>
        ) : (
          <Delta value={r.actualPct} size="xs" />
        ),
    },
    { key: "outcome", header: "Result", render: (r) => <OutcomeBadge report={r} /> },
    {
      key: "headline",
      header: "Headline",
      hideOnMobile: true,
      render: (r) => (
        <Text size="xs" c="dimmed" lineClamp={1} maw={360}>
          {r.headline}
        </Text>
      ),
    },
    { key: "delivery", header: "Delivery", hideOnMobile: true, render: deliverySummary },
    {
      key: "go",
      header: "",
      width: 32,
      align: "right",
      render: () => <LuChevronRight size={14} color="var(--kv2-text-muted)" />,
    },
  ];

  const toolbar = (
    <Group gap={8} wrap="wrap" style={{ flex: 1 }}>
      <TextInput
        aria-label="Search reports"
        placeholder="Search date or headline"
        leftSection={<LuSearch size={14} />}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        w={{ base: "100%", sm: 220 }}
      />
      <Select
        aria-label="Month"
        w={140}
        value={month}
        onChange={setMonth}
        allowDeselect={false}
        data={[
          { value: "all", label: "All months" },
          ...monthKeys.map((k) => ({ value: k, label: monthLabel(k) })),
        ]}
      />
      <SegmentedControl
        aria-label="Outlook"
        size="xs"
        value={outlook}
        onChange={setOutlook}
        data={[
          { value: "all", label: "All" },
          { value: "up", label: "▲ Up" },
          { value: "down", label: "▼ Down" },
          { value: "flat", label: "– Flat" },
          { value: "na", label: "N/A" },
        ]}
      />
      <Select
        aria-label="Result"
        w={130}
        value={outcome}
        onChange={setOutcome}
        allowDeselect={false}
        data={[
          { value: "all", label: "Any result" },
          { value: "hit", label: "Hit" },
          { value: "miss", label: "Miss" },
          { value: "pending", label: "Pending" },
        ]}
      />
      {filtersActive ? (
        <Button variant="subtle" size="xs" leftSection={<LuX size={12} />} onClick={clear}>
          Clear
        </Button>
      ) : null}
      <Text size="xs" c="dimmed" ml="auto" className="kv2-num">
        {filtered.length} of {reports.length} reports
      </Text>
    </Group>
  );

  const empty = (
    <EmptyState
      title={filtersActive ? "No reports match these filters" : "No reports yet"}
      description={
        filtersActive
          ? "Try another month or outlook, or clear the filters."
          : "The first report is built before the market opens on the next trading day."
      }

      action={
        filtersActive ? (
          <Button size="xs" variant="default" onClick={clear}>
            Clear filters
          </Button>
        ) : undefined
      }
    />
  );

  return (
    <Page>
      <PageHeader
        title="Daily reports"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "Reports" }]}
        description="Archive of the pre-open market brief sent by Telegram and email around 08:00 IST. Each report predicts the direction of the Sample Index 50 with a strength score from 0 (weak) to 10 (strong). All times IST."
        actions={
          <>
            {sampleUser.staff ? (
              <Button
                variant="default"
                leftSection={<LuRefreshCw size={14} />}
                onClick={() =>
                  notifications.show({
                    title: "Rebuild queued (sample)",
                    message: `Report for ${formatDate(latest.day)} will be rebuilt.`,
                  })
                }
              >
                Rebuild report
              </Button>
            ) : null}
            <Button
              variant="default"
              leftSection={<LuDownload size={14} />}
              onClick={() =>
                notifications.show({
                  title: "Export started (sample)",
                  message: `${filtered.length} reports exported as CSV.`,
                })
              }
            >
              Export CSV
            </Button>
          </>
        }
      />

      <Stack gap={16}>
        <KpiGrid>
          <KpiTile
            label="Latest report"
            value={
              <Anchor
                component={AppLink}
                href={`/v2/reports/${latest.day}/`}
                inherit
                c="var(--kv2-text)"
              >
                {formatDate(latest.day)}
              </Anchor>
            }
            aside={<OutlookBadge outlook={latest.outlook} size="xs" />}
            hint={
              latest.outlook === "na"
                ? "No outlook published"
                : `Strength ${latest.strength.toFixed(1)} / 10`
            }
          />
          <KpiTile
            label="Hit rate (90d)"
            value={<span className="kv2-num">{hitRate.toFixed(1)}%</span>}
            hint={`${settled.length} settled reports`}
            info="Share of reports whose predicted direction matched the actual close of the Sample Index 50. Flat means a move smaller than ±0.20%. Reports without an outlook are excluded."
          />
          <KpiTile
            label="Delivery today"
            value={
              <span className="kv2-num">
                {latestSent}/{latest.delivery.length} sent
              </span>
            }
            aside={
              <StatusBadge
                tone={latestSent === latest.delivery.length ? "gain" : "caution"}
                size="xs"
                dot
              >
                {latestSent === latest.delivery.length ? "Healthy" : "Check"}
              </StatusBadge>
            }
            hint="Telegram + email · 08:00 IST"
          />
          <KpiTile
            label={`${monthLabel(latestMonth)} mix`}
            value={<span className="kv2-num">{monthRows.length} sessions</span>}
            hint={`${monthRows.filter((r) => r.outlook === "up").length} ▲ · ${monthRows.filter((r) => r.outlook === "down").length} ▼ · ${monthRows.filter((r) => r.outlook === "flat" || r.outlook === "na").length} –`}
            info="How many reports this month predicted a rise, a fall, or a flat/unavailable outlook."
          />
        </KpiGrid>

        <Panel
          title="Report archive"
          info="Click a row to read the full brief and see delivery details. Result compares the predicted direction with the index close."
          actions={
            <SegmentedControl
              size="xs"
              aria-label="View"
              value={view}
              onChange={(v) => setView(v as "table" | "calendar")}
              data={[
                {
                  value: "table",
                  label: (
                    <Group gap={4} wrap="nowrap">
                      <LuTable size={12} /> Table
                    </Group>
                  ),
                },
                {
                  value: "calendar",
                  label: (
                    <Group gap={4} wrap="nowrap">
                      <LuCalendarDays size={12} /> Calendar
                    </Group>
                  ),
                },
              ]}
            />
          }
          flush
        >
          {view === "table" ? (
            <DataTable
              columns={columns}
              rows={filtered}
              rowKey={(r) => r.day}
              onRowClick={(r) => void navigate({ to: `/v2/reports/${r.day}/` })}
              toolbar={toolbar}
              empty={empty}
              totalLabel="reports"
            />
          ) : (
            <div>
              <div className="kv2-toolbar">{toolbar}</div>
              <Group px={12} pt={12} gap={8}>
                <Text fw={600} size="sm">
                  {monthLabel(calendarMonth)}
                </Text>
                {month === "all" ? (
                  <Text size="xs" c="dimmed">
                    Pick a month in the filter to browse others.
                  </Text>
                ) : null}
              </Group>
              <CalendarHeatmap month={calendarMonth} rows={filtered} />
            </div>
          )}
        </Panel>
      </Stack>
    </Page>
  );
}

export { ReportsPage } from "./DataDriven";
