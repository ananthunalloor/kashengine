import { Anchor, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";

import type { ReportDetail, ReportPage, ReportSummary } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const reportDate = new Intl.DateTimeFormat("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});
const deliveryDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function formatReportDate(day: string) {
  return reportDate.format(new Date(`${day}T00:00:00+05:30`));
}

export function ReportOutlook({ report }: { report: ReportSummary }) {
  if (!report.prediction) return null;
  const directions: Record<string, string> = { up: "Up", down: "Down", flat: "Flat" };
  return (
    <span className="report-outlook" data-tone={report.prediction}>
      {directions[report.prediction] ?? report.prediction}
      {report.strength !== null && `, strength ${report.strength}`}
    </span>
  );
}

export function ReportsList({ data, isStaff }: { data: ReportPage; isStaff: boolean }) {
  usePageTitle(`Reports${data.page > 1 ? ` - page ${data.page}` : ""}`);
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          Your daily perspective
        </Text>
        <Title order={1} tabIndex={-1}>
          Reports
        </Title>
        <Text c="dimmed" mt="sm" maw={720}>
          Daily reports sent on Telegram. Scores use a 1.0-10.0 scale; older reports with saved data
          are reformatted for viewing without changing the original text. Signal strength is not a
          probability of being right.
        </Text>
        <Anchor href="/reports/" size="sm">
          Compare with the existing Reports pages
        </Anchor>
      </header>
      {data.items.length ? (
        <ul className="report-list">
          {data.items.map((report) => (
            <li key={report.date} className="report-card">
              <Link to="/reports/$day/" params={{ day: report.date }} className="report-date">
                {formatReportDate(report.date)}
              </Link>
              <ReportOutlook report={report} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="report-card">
          <Text c="dimmed">
            There is no report yet. A report is built each trading day.
            {isStaff && (
              <>
                {" "}
                Admins: to build one now, use <Anchor href="/ops/jobs/">Ops &gt; Jobs</Anchor>{" "}
                ("Build the report again").
              </>
            )}
          </Text>
        </div>
      )}
      {data.pages > 1 && (
        <nav aria-label="Report pages" className="report-pagination">
          <span>
            {data.page > 1 && (
              <Link to="/reports/" search={{ page: data.page - 1 }}>
                Newer
              </Link>
            )}
          </span>
          <Text size="sm" c="dimmed">
            Page {data.page} of {data.pages}
          </Text>
          <span>
            {data.page < data.pages && (
              <Link to="/reports/" search={{ page: data.page + 1 }}>
                Older
              </Link>
            )}
          </span>
        </nav>
      )}
    </Stack>
  );
}

export function ReportView({ report }: { report: ReportDetail }) {
  usePageTitle(`Report ${formatReportDate(report.date)}`);
  return (
    <Stack gap="xl">
      <header>
        <Link to="/reports/" search={{ page: 1 }}>
          All reports
        </Link>
        <Text className="app-eyebrow" mt="lg" mb="xs">
          The market brief
        </Text>
        <Title order={1} tabIndex={-1}>
          {formatReportDate(report.date)}
        </Title>
        <Text mt="sm" component="div">
          <ReportOutlook report={report} />
        </Text>
      </header>
      <article aria-label="Report text" className="report-text">
        {report.text}
      </article>
      <section aria-labelledby="delivery-title">
        <Title order={2} id="delivery-title" size="h3" mb="sm">
          Delivery
        </Title>
        {report.deliveries.length ? (
          <ul className="report-deliveries">
            {report.deliveries.map((delivery) => (
              <li key={delivery.id}>
                <Text size="sm">
                  {delivery.channel},{" "}
                  <time dateTime={delivery.created_at}>
                    {deliveryDate.format(new Date(delivery.created_at))} IST
                  </time>
                </Text>
                <span className="report-status" data-tone={delivery.status}>
                  {delivery.status_label}
                </span>
                {delivery.error && (
                  <Text size="sm" className="report-diagnostic">
                    {delivery.error}
                  </Text>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Text size="sm" c="dimmed">
            This report was not sent.
          </Text>
        )}
      </section>
      <nav aria-label="Other reports" className="report-pagination">
        <span>
          {report.older && (
            <Link to="/reports/$day/" params={{ day: report.older }}>
              Older: {formatReportDate(report.older)}
            </Link>
          )}
        </span>
        <span>
          {report.newer && (
            <Link to="/reports/$day/" params={{ day: report.newer }}>
              Newer: {formatReportDate(report.newer)}
            </Link>
          )}
        </span>
      </nav>
    </Stack>
  );
}
