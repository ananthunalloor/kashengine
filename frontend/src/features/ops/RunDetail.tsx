import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import {
  LuActivity,
  LuArrowLeft,
  LuCircleCheck,
  LuCircleX,
  LuRefreshCw,
  LuTerminal,
} from "react-icons/lu";

import type { OpsRunDetail } from "../../shared/api/generated/types.gen";
import { stopRun } from "../../shared/api/ops";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { RunActor, RunStatus } from "./Runs";
import { OpsTime } from "./OpsTime";
import { AppLink } from "../../shared/ui/AppLink";

export function RunDetail({
  run,
  refreshing,
  onRefresh,
}: {
  run: OpsRunDetail;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState("");
  usePageTitle(`Task run - ${run.label}`);

  async function handleStop() {
    if (!run.is_active) return;
    setStopping(true);
    setStopError("");
    try {
      const result = await stopRun(String(run.id));
      if (!result.ok) {
        throw new Error("This task is no longer running.");
      }
      onRefresh();
    } catch (error) {
      setStopError(error instanceof Error ? error.message : "Could not stop this task.");
    } finally {
      setStopping(false);
    }
  }

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
          {run.is_active && (
            <Button
              size="compact-sm"
              color="red"
              variant="default"
              disabled={stopping}
              onClick={() => void handleStop()}
            >
              {stopping ? "Stopping..." : "Stop task"}
            </Button>
          )}
        </Group>
        {stopError && (
          <Text mt="sm" c="red">
            {stopError}
          </Text>
        )}
        {run.is_active && (
          <Text size="sm" c="dimmed" mt="sm">
            This run refreshes every 3 seconds while waiting or running.
          </Text>
        )}
        {run.status === "pending" && (
          <Text mt="sm">
            The job waits for a worker. If this does not change, check that a worker is running in{" "}
            <Anchor component={AppLink} href="/ops/">
              Ops Overview
            </Anchor>
            .
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
