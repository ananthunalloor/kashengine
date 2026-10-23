import { Alert, Anchor, Badge, Button, Group, Modal, Stack, Table, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { LuCalendarDays, LuClock } from "react-icons/lu";

import { calendarQuery } from "../api/calendar";
import type { TradingCalendar } from "../api/generated/types.gen";
import { sourceLink } from "./sourceLink";
import { formatReportDate } from "./formatReportDate";

function CalendarYear({ year, current }: { year: number; current: TradingCalendar }) {
  const query = useQuery({
    ...calendarQuery(year),
    enabled: year !== current.year,
  });
  const data = year === current.year ? current : query.data;
  if (query.isError && year !== current.year)
    return (
      <Alert color="red" title="Unable to load the calendar" role="alert">
        {query.error.message}
        <Button variant="subtle" onClick={() => void query.refetch()} ml="sm">
          Try again
        </Button>
      </Alert>
    );
  if (!data) return <Text role="status">Loading trading calendar...</Text>;
  if (!data.days.length)
    return (
      <Alert color="yellow" title="No dates published here" role="status">
        No holidays or special sessions have been added for {year}. This does not mean there are no
        exchange holidays. Check the official NSE calendar below.
      </Alert>
    );
  return (
    <Table.ScrollContainer minWidth={520}>
      <Table captionSide="top">
        <Table.Caption>
          Holidays and special trading sessions for {year}. All times are IST.
        </Table.Caption>
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">Date</Table.Th>
            <Table.Th scope="col">Session</Table.Th>
            <Table.Th scope="col">Reason</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.days.map((day) => (
            <Table.Tr key={day.day}>
              <Table.Td>
                <time dateTime={day.day}>{formatReportDate(day.day)}</time>
              </Table.Td>
              <Table.Td>
                <Badge color={day.kind === "holiday" ? "gray" : "blue"}>
                  {day.kind === "holiday" ? "Holiday" : "Special session"}
                </Badge>
                <Text size="sm" mt="xs">
                  {day.kind === "holiday" ? "Closed" : `${day.opens_at} - ${day.closes_at} IST`}
                </Text>
              </Table.Td>
              <Table.Td>
                {day.reason}
                {sourceLink(day.source_url) && (
                  <Text size="sm">
                    <Anchor
                      href={sourceLink(day.source_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Exchange circular
                    </Anchor>
                  </Text>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export function MarketCalendar({
  calendar,
  canManage,
}: {
  calendar: TradingCalendar;
  canManage: boolean;
}) {
  const [opened, setOpened] = useState(false);
  const [year, setYear] = useState(calendar.year);
  const [dismissed, setDismissed] = useState("");
  const showAlert = !calendar.is_open || Boolean(calendar.special_reason);
  return (
    <>
      <Group justify="space-between" mb="md">
        <Text size="sm" c="dimmed">
          NSE cash/equity · Scheduled {calendar.is_open ? "open" : "closed"} · IST
        </Text>
        <Button
          variant="subtle"
          leftSection={<LuCalendarDays aria-hidden="true" />}
          onClick={() => {
            setYear(calendar.year);
            setOpened(true);
          }}
        >
          Trading calendar
        </Button>
      </Group>
      {showAlert && dismissed !== calendar.status_key && (
        <Alert
          color={calendar.is_open ? "blue" : "yellow"}
          title={calendar.is_open ? "Special trading session" : "Market closed"}
          icon={<LuClock aria-hidden="true" />}
          withCloseButton
          closeButtonLabel="Dismiss market notice"
          onClose={() => setDismissed(calendar.status_key)}
          role="status"
          mb="md"
        >
          {calendar.reason}
          {calendar.special_reason && calendar.special_reason !== calendar.reason && (
            <> {calendar.special_reason}</>
          )}{" "}
          This is the scheduled NSE equity status, not a live exchange feed.{" "}
          <Anchor component="button" type="button" onClick={() => setOpened(true)}>
            View holidays and special sessions
          </Anchor>
        </Alert>
      )}
      {opened && (
        <Modal
          opened
          onClose={() => setOpened(false)}
          title="NSE trading calendar"
          size="lg"
          lockScroll={false}
          transitionProps={{ duration: 0 }}
          classNames={{ content: "trading-calendar-dialog" }}
          closeButtonProps={{ "aria-label": "Close trading calendar" }}
        >
          <Stack>
            <Text size="sm" c="dimmed">
              Staff-maintained NSE cash/equity calendar. Unlisted weekdays are assumed to trade
              09:15 - 15:30 IST (or the configured closing time). Weekends are closed unless a
              special session is listed. Dates may change; verify exchange announcements.
            </Text>
            <Group justify="space-between" wrap="nowrap" gap="xs">
              <Button
                variant="default"
                px="xs"
                aria-label="Previous year"
                disabled={year <= 2000}
                onClick={() => setYear(year - 1)}
              >
                Previous
              </Button>
              <Text fw={600} aria-live="polite">
                {year}
              </Text>
              <Button
                variant="default"
                px="xs"
                aria-label="Next year"
                disabled={year >= 2100}
                onClick={() => setYear(year + 1)}
              >
                Next
              </Button>
            </Group>
            <CalendarYear year={year} current={calendar} />
            <Anchor href={calendar.source_url} target="_blank" rel="noopener noreferrer">
              Official NSE holiday calendar
            </Anchor>
            {canManage && (
              <Anchor href="/admin/markets/tradingcalendarday/">
                Manage holidays and special sessions
              </Anchor>
            )}
          </Stack>
        </Modal>
      )}
    </>
  );
}
