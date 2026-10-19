import { Anchor, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";

import type { DeliveryPage } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";

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
          From the report to your inbox
        </Text>
        <Title order={1} tabIndex={-1}>
          Delivery
        </Title>
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
        {data.items.length ? (
          <ul className="news-list">
            {data.items.map((attempt) => {
              const label = attempt.report_date
                ? reportDate.format(new Date(`${attempt.report_date}T00:00:00+05:30`))
                : "Test";
              return (
                <li key={attempt.id} className="news-card">
                  <div className="news-card-heading">
                    <Title order={3} size="h4">
                      <time dateTime={attempt.created_at}>
                        {attemptDate.format(new Date(attempt.created_at))} IST
                      </time>
                    </Title>
                    <span className="report-status" data-tone={attempt.status}>
                      {attempt.status_label}
                    </span>
                  </div>
                  <dl className="delivery-facts">
                    <div>
                      <dt>Channel</dt>
                      <dd>{attempt.channel}</dd>
                    </div>
                    <div>
                      <dt>Report</dt>
                      <dd>
                        {attempt.report_date && canReadReports ? (
                          <Link to="/reports/$day/" params={{ day: attempt.report_date }}>
                            {label}
                          </Link>
                        ) : (
                          label
                        )}
                      </dd>
                    </div>
                  </dl>
                  {isStaff && attempt.error && (
                    <Text className="report-diagnostic" size="sm" mt="sm">
                      {attempt.error}
                    </Text>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <Text c="dimmed">Nothing was sent yet.</Text>
        )}
      </section>
    </Stack>
  );
}
