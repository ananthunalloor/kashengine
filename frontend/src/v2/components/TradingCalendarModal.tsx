import {
  ActionIcon,
  Group,
  Modal,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";

import { calendarQuery } from "../../shared/api/calendar";
import type { TradingCalendarEntry } from "../../shared/api/generated/types.gen";
import { DataTable } from "./DataTable";
import { KpiGrid, KpiTile } from "./Layout";
import { ErrorState, SkeletonRows } from "./States";
import { StatusBadge } from "./Status";
import { formatDate } from "./format";

const monthNames = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const weekdays = ["S", "M", "T", "W", "T", "F", "S"];

function MonthGrid({
  year,
  month,
  sessions,
}: {
  year: number;
  month: number;
  sessions: TradingCalendarEntry[];
}) {
  const first = new Date(Date.UTC(year, month, 1)).getUTCDay();
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const byDay = new Map(
    sessions
      .filter((s) => Number(s.day.slice(5, 7)) === month + 1)
      .map((s) => [Number(s.day.slice(8, 10)), s]),
  );
  const holidays = [...byDay.values()].filter((s) => s.kind === "holiday").length;
  return (
    <div className="kv2-panel" style={{ padding: 8 }}>
      <Group justify="space-between" mb={4}>
        <Text size="xs" fw={600}>
          {monthNames[month]}
        </Text>
        {holidays ? (
          <Text size="xs" c="var(--kv2-loss)">
            {holidays} hol
          </Text>
        ) : null}
      </Group>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2 }}>
        {weekdays.map((d, i) => (
          <Text key={i} size="10px" c="dimmed" ta="center">
            {d}
          </Text>
        ))}
        {Array.from({ length: first }, (_, i) => (
          <span key={`b${i}`} />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const day = i + 1;
          const weekday = (first + i) % 7;
          const session = byDay.get(day);
          const bg =
            session?.kind === "holiday"
              ? "var(--kv2-loss-soft)"
              : session?.kind === "special"
                ? "var(--kv2-gain-soft)"
                : undefined;
          const color =
            session?.kind === "holiday"
              ? "var(--kv2-loss)"
              : session?.kind === "special"
                ? "var(--kv2-gain)"
                : weekday === 0 || weekday === 6
                  ? "var(--mantine-color-placeholder)"
                  : undefined;
          const cell = (
            <Text
              size="10px"
              ta="center"
              className="kv2-num"
              fw={session ? 700 : 400}
              style={{ background: bg, color, borderRadius: 3, lineHeight: "16px" }}
            >
              {day}
            </Text>
          );
          return session ? (
            <Tooltip
              key={day}
              label={`${session.reason} · ${session.opens_at}–${session.closes_at}`}
            >
              {cell}
            </Tooltip>
          ) : (
            <span key={day}>{cell}</span>
          );
        })}
      </div>
    </div>
  );
}

/** NSE/BSE trading calendar: summary, annual grid, session list. Opened from the market pill. */
export function TradingCalendarModal({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [view, setView] = useState("grid");
  const query = useQuery({ ...calendarQuery(year), enabled: opened });
  const sessions = query.data?.days ?? [];
  const holidays = sessions.filter((s) => s.kind === "holiday");
  const special = sessions.filter((s) => s.kind === "special");

  return (
    <Modal opened={opened} onClose={onClose} size={960} title="Trading calendar · NSE & BSE">
      <Stack gap={12}>
        {query.isPending ? <SkeletonRows rows={4} /> : null}
        {query.error ? <ErrorState onRetry={() => void query.refetch()} /> : null}
        {query.data ? (
          <>
            <Text size="xs" c="dimmed">
              {query.data.reason}
              {query.data.special_reason ? ` · ${query.data.special_reason}` : ""} · Updated{" "}
              {formatDate(query.data.as_of)}
            </Text>
            <KpiGrid cols={3}>
              <KpiTile label="Trading holidays" value={holidays.length} hint="Weekday closures" />
              <KpiTile label="Special sessions" value={special.length} hint="e.g. Muhurat" />
              <KpiTile
                label="Next holiday"
                value={<Text fw={600}>{holidays[0] ? formatDate(holidays[0].day) : "—"}</Text>}
                hint={holidays[0]?.reason}
              />
            </KpiGrid>
            <Group justify="space-between">
              <Group gap={4}>
                <ActionIcon aria-label="Previous year" onClick={() => setYear((y) => y - 1)}>
                  <LuChevronLeft />
                </ActionIcon>
                <Text fw={600} className="kv2-num" w={44} ta="center">
                  {year}
                </Text>
                <ActionIcon aria-label="Next year" onClick={() => setYear((y) => y + 1)}>
                  <LuChevronRight />
                </ActionIcon>
              </Group>
              <Group gap={8}>
                <StatusBadge tone="loss" size="xs">
                  Holiday
                </StatusBadge>
                <StatusBadge tone="gain" size="xs">
                  Special session
                </StatusBadge>
                <SegmentedControl
                  data={[
                    { value: "grid", label: "Year" },
                    { value: "list", label: "List" },
                  ]}
                  value={view}
                  onChange={setView}
                />
              </Group>
            </Group>
            {view === "grid" ? (
              <SimpleGrid cols={{ base: 2, sm: 4, md: 6 }} spacing={8}>
                {monthNames.map((_, m) => (
                  <MonthGrid key={m} year={year} month={m} sessions={sessions} />
                ))}
              </SimpleGrid>
            ) : (
              <div className="kv2-panel">
                <DataTable
                  rows={sessions}
                  rowKey={(s) => s.day}
                  paginate={false}
                  columns={[
                    { key: "date", header: "Date (IST)", render: (s) => formatDate(s.day) },
                    {
                      key: "type",
                      header: "Session",
                      render: (s) =>
                        s.kind === "holiday" ? (
                          <StatusBadge tone="loss">▼ Holiday</StatusBadge>
                        ) : (
                          <StatusBadge tone="gain">▲ Special</StatusBadge>
                        ),
                    },
                    { key: "name", header: "Reason", render: (s) => s.reason },
                    {
                      key: "hours",
                      header: "Hours",
                      render: (s) => `${s.opens_at}–${s.closes_at}`,
                    },
                  ]}
                />
              </div>
            )}
            <Text size="xs" c="dimmed">
              Exchange calendar exceptions are maintained by the server. Times are shown in IST
              (UTC+05:30).
            </Text>
          </>
        ) : null}
      </Stack>
    </Modal>
  );
}
