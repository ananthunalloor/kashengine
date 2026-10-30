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
import { useState } from "react";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";

import { DataTable } from "./DataTable";
import { KpiGrid, KpiTile } from "./Layout";
import { StatusBadge } from "./Status";
import { formatDate } from "./format";
import { calendarSessions } from "../mock/data";
import type { CalendarSession } from "../mock/data";

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
  sessions: CalendarSession[];
}) {
  const first = new Date(Date.UTC(year, month, 1)).getUTCDay();
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const byDay = new Map(
    sessions
      .filter((s) => Number(s.date.slice(5, 7)) === month + 1)
      .map((s) => [Number(s.date.slice(8, 10)), s]),
  );
  const holidays = [...byDay.values()].filter((s) => s.type === "holiday").length;
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
            session?.type === "holiday"
              ? "var(--kv2-loss-soft)"
              : session?.type === "special"
                ? "var(--kv2-gain-soft)"
                : undefined;
          const color =
            session?.type === "holiday"
              ? "var(--kv2-loss)"
              : session?.type === "special"
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
            <Tooltip key={day} label={`${session.name} · ${session.hours}`}>
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
  const [year, setYear] = useState(2026);
  const [view, setView] = useState("grid");
  const sessions = calendarSessions.filter((s) => s.date.startsWith(String(year)));
  const holidays = sessions.filter((s) => s.type === "holiday");
  const special = sessions.filter((s) => s.type === "special");

  return (
    <Modal opened={opened} onClose={onClose} size={960} title="Trading calendar · NSE & BSE">
      <Stack gap={12}>
        <KpiGrid cols={3}>
          <KpiTile label="Trading holidays" value={holidays.length} hint="Weekday closures" />
          <KpiTile label="Special sessions" value={special.length} hint="e.g. Muhurat" />
          <KpiTile
            label="Next holiday"
            value={<Text fw={600}>{holidays[0] ? formatDate(holidays[0].date) : "—"}</Text>}
            hint={holidays[0]?.name}
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
              rowKey={(s) => s.date}
              paginate={false}
              columns={[
                { key: "date", header: "Date (IST)", render: (s) => formatDate(s.date) },
                {
                  key: "type",
                  header: "Session",
                  render: (s) =>
                    s.type === "holiday" ? (
                      <StatusBadge tone="loss">▼ Holiday</StatusBadge>
                    ) : (
                      <StatusBadge tone="gain">▲ Special</StatusBadge>
                    ),
                },
                { key: "name", header: "Reason", render: (s) => s.name },
                { key: "hours", header: "Hours", render: (s) => s.hours },
              ]}
            />
          </div>
        )}
        <Text size="xs" c="dimmed">
          Sample calendar for layout only. Times in IST (UTC+05:30).
        </Text>
      </Stack>
    </Modal>
  );
}
