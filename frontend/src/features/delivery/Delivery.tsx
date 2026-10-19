import { Anchor, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { LuSend } from "react-icons/lu";

import type { DeliveryPage } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { DataTable } from "../../shared/ui/DataTable";

const attemptDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const reportDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function Delivery({
  data,
  isStaff,
  canReadReports,
}: {
  data: DeliveryPage;
  isStaff: boolean;
  canReadReports: boolean;
}) {
  usePageTitle("Delivery");
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuSend aria-hidden="true" />
          From the report to your inbox
        </Text>
        <Title order={1}>Delivery</Title>
        <Text c="dimmed" mt="sm">
          {data.chat_count ? (
            <>
              The report goes to {data.chat_count} Telegram chat{data.chat_count === 1 ? "" : "s"}.
            </>
          ) : isStaff ? (
            <>
              No Telegram chat is set. Set the bot token and the chat IDs in{" "}
              <Anchor href="/ops/settings/telegram/">Ops &gt; Settings &gt; Telegram</Anchor>. You
              can send a test message there.
            </>
          ) : (
            "The daily report is not sent to Telegram yet."
          )}
        </Text>
        <Anchor href="/delivery/" size="sm">
          Compare with the existing Delivery page
        </Anchor>
      </header>
      <section aria-labelledby="delivery-attempts">
        <Title order={2} id="delivery-attempts" size="h3">
          Latest attempts
        </Title>
        <Text c="dimmed" size="sm" mt="sm" mb="md">
          The newest 50 send attempts. Times are in IST.
        </Text>
        <DataTable
          data={data.items}
          label="Delivery attempts (latest 50)"
          initialSort={[{ id: "created_at", desc: true }]}
          filters={[
            { label: "Status", value: (row) => row.status_label, options: ["Sent", "Failed"] },
            { label: "Channel", value: (row) => row.channel, options: ["Telegram", "Email"] },
          ]}
          columns={[
            {
              id: "created_at",
              label: "Time (IST)",
              value: (row) => row.created_at,
              render: (row) => (
                <time dateTime={row.created_at}>
                  {attemptDate.format(new Date(row.created_at))} IST
                </time>
              ),
            },
            {
              id: "channel",
              label: "Channel",
              value: (row) => row.channel,
              render: (row) => <span className="symbol-chip">{row.channel}</span>,
            },
            {
              id: "report",
              label: "Report",
              value: (row) => row.report_date ?? "Test",
              render: (row) => {
                const label = row.report_date
                  ? reportDate.format(new Date(`${row.report_date}T00:00:00+05:30`))
                  : "Test";
                return row.report_date && canReadReports ? (
                  <Link to="/reports/$day/" params={{ day: row.report_date }}>
                    {label}
                  </Link>
                ) : (
                  label
                );
              },
            },
            {
              id: "status",
              label: "Result",
              value: (row) => row.status_label,
              render: (row) => (
                <span className="report-status" data-tone={row.status}>
                  {row.status_label}
                </span>
              ),
            },
            ...(isStaff
              ? [
                  {
                    id: "error",
                    label: "Diagnostics",
                    value: (row: DeliveryPage["items"][number]) => row.error,
                    render: (row: DeliveryPage["items"][number]) =>
                      row.error ? (
                        <Text className="report-diagnostic" size="sm">
                          {row.error}
                        </Text>
                      ) : (
                        "Not available"
                      ),
                  },
                ]
              : []),
          ]}
          empty={
            <Text c="dimmed">
              {data.items.length
                ? "No attempts match. Clear the search or filters."
                : "Nothing was sent yet."}
            </Text>
          }
        />
      </section>
    </Stack>
  );
}
