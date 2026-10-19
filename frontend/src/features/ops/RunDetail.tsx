import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import {
  LuActivity,
  LuArrowLeft,
  LuCircleCheck,
  LuCircleX,
  LuRefreshCw,
  LuTerminal,
} from "react-icons/lu";

import type { OpsRunDetail } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { RunActor, RunStatus } from "./Runs";
import { OpsTime } from "./OpsTime";

export function RunDetail({
  run,
  refreshing,
  onRefresh,
}: {
  run: OpsRunDetail;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  usePageTitle(`Task run - ${run.label}`);
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuActivity aria-hidden="true" /> Operations / run details
        </Text>
        <Title order={1} className="ops-page-title">
          <LuActivity aria-hidden="true" />
          {run.label}
        </Title>
        <Group mt="md">
          <RunStatus run={run} />
          <Button
            size="compact-sm"
            variant="default"
            leftSection={<LuRefreshCw aria-hidden="true" />}
            disabled={refreshing}
            onClick={onRefresh}
          >
            {refreshing ? "Refreshing..." : "Refresh now"}
          </Button>
        </Group>
        {run.is_active && (
          <Text size="sm" c="dimmed" mt="sm">
            This run refreshes every 3 seconds while waiting or running.
          </Text>
        )}
        {run.status === "pending" && (
          <Text mt="sm">
            The job waits for a worker. If this does not change, check that a worker is running in{" "}
            <Anchor href="/ops/">Ops Overview</Anchor>.
          </Text>
        )}
        <Group mt="md">
          <Link to="/ops/runs/" search={{ q: "", label: "", status: "", trigger: "", page: 1 }}>
            <LuArrowLeft aria-hidden="true" /> Back to task runs
          </Link>
        </Group>
      </header>
      <section className="news-card" aria-label="Run metadata">
        <dl className="ops-run-facts">
          <div>
            <dt>Queued</dt>
            <dd>
              <OpsTime value={run.created_at} />
            </dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>
              <OpsTime value={run.started_at} />
            </dd>
          </div>
          <div>
            <dt>Finished</dt>
            <dd>
              <OpsTime value={run.finished_at} />
            </dd>
          </div>
          <div>
            <dt>Time</dt>
            <dd>{run.duration}</dd>
          </div>
          <div>
            <dt>Started by</dt>
            <dd>
              <RunActor run={run} />
            </dd>
          </div>
          <div>
            <dt>Worker</dt>
            <dd>{run.worker || "\u2013"}</dd>
          </div>
          <div>
            <dt>Task</dt>
            <dd>
              <code>{run.task_name}</code>
            </dd>
          </div>
          <div>
            <dt>Task ID</dt>
            <dd>
              <code>{run.task_id}</code>
            </dd>
          </div>
          {run.args && (
            <div>
              <dt>Arguments</dt>
              <dd>
                <code>{run.args}</code>
              </dd>
            </div>
          )}
        </dl>
      </section>
      {(["error", "result", "output"] as const).map(
        (field) =>
          run[field] && (
            <section
              key={field}
              className={`ops-output ops-output-${field === "result" && run.status !== "success" ? "output" : field}`}
              aria-labelledby={`run-${field}`}
            >
              <Title order={2} size="h3" id={`run-${field}`} className="ops-section-title">
                {field === "error" ? (
                  <LuCircleX aria-hidden="true" />
                ) : field === "result" && run.status === "success" ? (
                  <LuCircleCheck aria-hidden="true" />
                ) : (
                  <LuTerminal aria-hidden="true" />
                )}
                {field.charAt(0).toUpperCase() + field.slice(1)}
              </Title>
              <pre className="report-text">{run[field]}</pre>
            </section>
          ),
      )}
    </Stack>
  );
}
