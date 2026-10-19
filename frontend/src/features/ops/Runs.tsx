import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuActivity, LuSearch, LuX } from "react-icons/lu";

import type { OpsRunPage, OpsRunSummary } from "../../shared/api/generated/types.gen";
import type { RunSearch } from "../../shared/api/ops";
import { DataTable } from "../../shared/ui/DataTable";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const runDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function RunTime({ value }: { value: string | null }) {
  return value ? <time dateTime={value}>{runDate.format(new Date(value))} IST</time> : "\u2013";
}

export function RunStatus({ run }: { run: Pick<OpsRunSummary, "status" | "status_label"> }) {
  return (
    <span
      className="report-status"
      data-tone={
        run.status === "success"
          ? "sent"
          : run.status === "failure"
            ? "failed"
            : run.status === "pending"
              ? "warning"
              : undefined
      }
    >
      {run.status_label}
    </span>
  );
}

export function RunActor({ run }: { run: Pick<OpsRunSummary, "trigger" | "triggered_by"> }) {
  return run.trigger === "manual"
    ? run.triggered_by || "An admin (deleted)"
    : "Schedule or another task";
}

export function Runs({
  data,
  filters,
  onFilter,
}: {
  data: OpsRunPage;
  filters: RunSearch;
  onFilter: (filters: RunSearch, replace?: boolean) => void;
}) {
  usePageTitle(`Task runs${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const searchInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setQuery(filters.q);
    return () => clearTimeout(timer.current);
  }, [
    filters.q,
    filters.label,
    filters.status,
    filters.trigger,
    filters.page,
    filters.page_size,
    filters.sort,
  ]);
  function change(values: RunSearch, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...values, q: query.trim(), page: 1 }, replace);
  }
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuActivity aria-hidden="true" /> Operations / execution history
        </Text>
        <Title order={1} tabIndex={-1}>
          Task runs
        </Title>
        <Text c="dimmed" mt="sm">
          Every recorded task or command, with its time and result. Old runs are deleted after{" "}
          {data.retention_days} days.
        </Text>
        <Group mt="sm">
          <Anchor href="/ops/runs/" size="sm">
            Compare with the original Runs page
          </Anchor>
          <Anchor href="/ops/jobs/" size="sm">
            Manage jobs in Ops
          </Anchor>
        </Group>
      </header>
      <form
        className="news-filters ops-run-filters"
        onSubmit={(event) => {
          event.preventDefault();
          change(filters);
        }}
      >
        <div>
          <label htmlFor="run-query">Search jobs, task IDs, or users</label>
          <input
            id="run-query"
            type="search"
            maxLength={200}
            autoComplete="off"
            ref={searchInput}
            value={query}
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(
                () => onFilter({ ...filters, q: value.trim(), page: 1 }, true),
                300,
              );
            }}
          />
        </div>
        <div>
          <label htmlFor="run-label">Job</label>
          <select
            id="run-label"
            value={filters.label}
            onChange={(event) => change({ ...filters, label: event.target.value })}
          >
            <option value="">All jobs</option>
            {filters.label && !data.labels.includes(filters.label) && (
              <option>{filters.label}</option>
            )}
            {data.labels.map((label) => (
              <option key={label}>{label}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="run-status">Result</label>
          <select
            id="run-status"
            value={filters.status}
            onChange={(event) =>
              change({ ...filters, status: event.target.value as RunSearch["status"] })
            }
          >
            <option value="">All results</option>
            <option value="pending">Waiting</option>
            <option value="started">Running</option>
            <option value="success">Done</option>
            <option value="failure">Failed</option>
          </select>
        </div>
        <div>
          <label htmlFor="run-trigger">Started by</label>
          <select
            id="run-trigger"
            value={filters.trigger}
            onChange={(event) =>
              change({ ...filters, trigger: event.target.value as RunSearch["trigger"] })
            }
          >
            <option value="">All triggers</option>
            <option value="auto">Automatic</option>
            <option value="manual">Manual</option>
          </select>
        </div>
        <Group gap="xs">
          <Button type="submit" leftSection={<LuSearch aria-hidden="true" />}>
            Search
          </Button>
          <Button
            type="button"
            variant="default"
            leftSection={<LuX aria-hidden="true" />}
            onClick={() => {
              clearTimeout(timer.current);
              setQuery("");
              onFilter({ ...filters, q: "", label: "", status: "", trigger: "", page: 1 });
              searchInput.current?.focus();
            }}
          >
            Clear filters
          </Button>
        </Group>
      </form>
      <DataTable
        data={data.items}
        label="Task runs"
        empty="No runs match these filters."
        columns={[
          {
            id: "label",
            label: "Job",
            value: (run) => run.label,
            render: (run) => (
              <Link to="/ops/runs/$id/" params={{ id: String(run.id) }}>
                {run.label}
              </Link>
            ),
          },
          {
            id: "started_at",
            label: "Started",
            value: (run) => run.started_at ?? run.created_at,
            render: (run) => <RunTime value={run.started_at ?? run.created_at} />,
          },
          {
            id: "duration_ms",
            label: "Time",
            value: (run) => run.duration_ms,
            render: (run) => run.duration,
          },
          {
            id: "trigger",
            label: "Started by",
            value: (run) => run.trigger,
            render: (run) => <RunActor run={run} />,
          },
          {
            id: "status",
            label: "Result",
            value: (run) => run.status,
            render: (run) => <RunStatus run={run} />,
          },
        ]}
        server={{
          page: data.page,
          pages: data.pages,
          total: data.total,
          pageSize: data.page_size,
          sort: filters.sort,
          onSort: (sort) => change({ ...filters, sort }),
          onPageSize: (page_size) => change({ ...filters, page_size }),
          paginationLabel: "Task history pages",
          pageLink: (page, label) => (
            <Link to="/ops/runs/" search={{ ...filters, page }}>
              {label}
            </Link>
          ),
        }}
      />
    </Stack>
  );
}
