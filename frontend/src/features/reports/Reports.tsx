import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuFileText, LuSearch, LuX } from "react-icons/lu";

import type { ReportDetail, ReportPage, ReportSummary } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { DataTable } from "../../shared/ui/DataTable";
import { MetricValue, StrengthLegend } from "../../shared/ui/MetricValue";
import { formatReportDate } from "../../shared/ui/formatReportDate";
import { reportSearchSchema } from "../../shared/api/reports";
import type { ReportSearch } from "../../shared/api/reports";

const deliveryDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function ReportOutlook({ report }: { report: ReportSummary }) {
  if (!report.prediction) return null;
  const directions: Record<string, string> = { up: "Up", down: "Down", flat: "Flat" };
  return (
    <span className="report-outlook" data-tone={report.prediction}>
      {directions[report.prediction] ?? report.prediction}
      {report.strength !== null && (
        <>
          , strength <MetricValue kind="strength" value={report.strength} />
        </>
      )}
    </span>
  );
}

export function ReportsList({
  data,
  isStaff,
  filters,
  onFilter,
}: {
  data: ReportPage;
  isStaff: boolean;
  filters: ReportSearch;
  onFilter: (filters: ReportSearch, replace?: boolean) => void;
}) {
  usePageTitle(`Reports${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q ?? "");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    setQuery(filters.q ?? "");
    return () => clearTimeout(timer.current);
  }, [filters.q, filters.page, filters.direction, filters.sort, filters.page_size]);
  function apply(q: string, direction = filters.direction, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...filters, q: q.trim(), direction, page: 1 }, replace);
  }
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuFileText aria-hidden="true" />
          Your daily perspective
        </Text>
        <Title order={1}>Reports</Title>
        <Text c="dimmed" mt="sm" maw={720}>
          Daily reports sent on Telegram. Scores use a 1.0-10.0 scale; older reports with saved data
          are reformatted for viewing without changing the original text. Signal strength is not a
          probability of being right. <StrengthLegend />
        </Text>
        <Anchor href="/reports/" size="sm">
          Compare with the existing Reports pages
        </Anchor>
      </header>
      <form
        className="news-filters report-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply(query);
        }}
      >
        <div>
          <label htmlFor="report-query">Search reports</label>
          <input
            id="report-query"
            type="search"
            maxLength={100}
            value={query}
            placeholder="Search date or report text..."
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => apply(value, filters.direction, true), 300);
            }}
          />
        </div>
        <div>
          <label htmlFor="report-direction">Outlook</label>
          <select
            id="report-direction"
            value={filters.direction ?? ""}
            onChange={(event) =>
              apply(query, reportSearchSchema.shape.direction.parse(event.target.value))
            }
          >
            <option value="">All outlooks</option>
            <option value="up">Up</option>
            <option value="down">Down</option>
            <option value="flat">Flat</option>
            <option value="unknown">Not available</option>
          </select>
        </div>
        <Group>
          <Button type="submit" leftSection={<LuSearch aria-hidden="true" />}>
            Search
          </Button>
          <Button
            variant="default"
            leftSection={<LuX aria-hidden="true" />}
            type="button"
            onClick={() => {
              setQuery("");
              apply("", "");
            }}
          >
            Clear filters
          </Button>
        </Group>
      </form>
      <DataTable
        data={data.items}
        label="Reports"
        columns={[
          {
            id: "date",
            label: "Report date",
            value: (row) => row.date,
            render: (row) => (
              <Link to="/reports/$day/" params={{ day: row.date }} className="report-date">
                {formatReportDate(row.date)}
              </Link>
            ),
          },
          {
            id: "prediction",
            label: "Outlook",
            value: (row) => row.prediction,
            render: (row) =>
              row.prediction ? (
                <ReportOutlook report={{ ...row, strength: null }} />
              ) : (
                "Not available"
              ),
          },
          {
            id: "strength",
            label: "Strength",
            value: (row) => row.strength,
            render: (row) => <MetricValue kind="strength" value={row.strength} />,
          },
        ]}
        server={{
          page: data.page,
          pages: data.pages,
          total: data.total,
          pageSize: data.page_size ?? 25,
          sort: filters.sort,
          onSort: (sort) => {
            clearTimeout(timer.current);
            onFilter({ ...filters, q: query.trim(), sort, page: 1 });
          },
          onPageSize: (page_size) => {
            clearTimeout(timer.current);
            onFilter({ ...filters, q: query.trim(), page_size, page: 1 });
          },
          paginationLabel: "Report pages",
          pageLink: (page, label) => (
            <Link to="/reports/" search={{ ...filters, page }}>
              {label}
            </Link>
          ),
        }}
        empty={
          <Text c="dimmed">
            {filters.q || filters.direction
              ? "No report matches. Change the search or filters."
              : "There is no report yet. A report is built each trading day."}
            {isStaff && !filters.q && !filters.direction && (
              <>
                {" "}
                Admins: to build one now, use <Anchor href="/ops/jobs/">Ops &gt; Jobs</Anchor>{" "}
                ("Build the report again").
              </>
            )}
          </Text>
        }
      />
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
        <Title order={1}>{formatReportDate(report.date)}</Title>
        <Text mt="sm" component="div">
          <ReportOutlook report={report} />
        </Text>
        {report.strength !== null && (
          <Text size="sm" c="dimmed" mt="sm">
            <StrengthLegend />
          </Text>
        )}
      </header>
      <article aria-label="Report text" className="report-text">
        {report.text}
      </article>
      <section aria-labelledby="delivery-title">
        <Title order={2} id="delivery-title" size="h3" mb="sm">
          Delivery
        </Title>
        {report.deliveries.length ? (
          <DataTable
            data={report.deliveries}
            label="Report delivery"
            filters={[
              { label: "Status", value: (row) => row.status_label, options: ["Sent", "Failed"] },
            ]}
            columns={[
              {
                id: "created_at",
                label: "Time (IST)",
                value: (row) => row.created_at,
                render: (row) => (
                  <time dateTime={row.created_at}>
                    {deliveryDate.format(new Date(row.created_at))} IST
                  </time>
                ),
              },
              { id: "channel", label: "Channel", value: (row) => row.channel },
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
              {
                id: "error",
                label: "Diagnostics",
                value: (row) => row.error,
                render: (row) =>
                  row.error ? (
                    <Text size="sm" className="report-diagnostic">
                      {row.error}
                    </Text>
                  ) : (
                    "Not available"
                  ),
              },
            ]}
          />
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
