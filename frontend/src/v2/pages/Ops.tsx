import {
  ActionIcon,
  Anchor,
  Button,
  Code,
  Group,
  Menu,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
  Timeline,
  Tooltip,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { useMemo, useState } from "react";
import {
  LuArrowDownToLine,
  LuCircleCheck,
  LuCircleHelp,
  LuEllipsis,
  LuFilePlus2,
  LuFilter,
  LuPlay,
  LuRefreshCw,
  LuSearch,
  LuTriangleAlert,
} from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  EmptyState,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components";
import type { Column, Tone } from "../components";
import { mockSeries } from "../mock/generate";

type OpsRow = {
  id: string;
  name: string;
  detail: string;
  status: string;
  updated: string;
  owner: string;
  value: number;
};

const pages = [
  { key: "overview", label: "Overview", path: "/v2/ops/" },
  { key: "jobs", label: "Jobs & queues", path: "/v2/ops/jobs/" },
  { key: "runs", label: "Task runs", path: "/v2/ops/runs/" },
  { key: "logs", label: "Logs", path: "/v2/ops/logs/" },
  { key: "smtp", label: "SMTP queue", path: "/v2/ops/smtp/" },
  { key: "metrics", label: "Metrics", path: "/v2/ops/metrics/" },
  { key: "schedule", label: "Schedule", path: "/v2/ops/schedule/" },
  { key: "users", label: "Users", path: "/v2/ops/users/" },
  { key: "invites", label: "Invite codes", path: "/v2/ops/invites/" },
  { key: "subscriptions", label: "Subscriptions", path: "/v2/ops/subscriptions/" },
  { key: "logins", label: "Logins & lockouts", path: "/v2/ops/logins/" },
  { key: "audit", label: "Audit trail", path: "/v2/ops/audit/" },
  { key: "feeds", label: "Feeds", path: "/v2/ops/feeds/" },
  { key: "instruments", label: "Instruments", path: "/v2/ops/instruments/" },
  { key: "config", label: "Configuration", path: "/v2/ops/config/" },
  { key: "backups", label: "Backups", path: "/v2/ops/backups/" },
];

const statuses: Record<string, Tone> = {
  Healthy: "gain",
  Active: "gain",
  Completed: "gain",
  Sent: "gain",
  Enabled: "gain",
  Pending: "caution",
  Queued: "caution",
  "In progress": "info",
  Paused: "neutral",
  Disabled: "neutral",
  Failed: "loss",
  Locked: "loss",
};

const seedRows: Record<string, OpsRow[]> = {
  overview: [
    {
      id: "run-8401",
      name: "Daily brief assembly",
      detail: "Sample research workflow",
      status: "Completed",
      updated: "05:10 IST",
      owner: "Scheduler",
      value: 4.2,
    },
    {
      id: "run-8400",
      name: "Feed ingestion",
      detail: "12 sample sources checked",
      status: "Completed",
      updated: "05:02 IST",
      owner: "Scheduler",
      value: 2.8,
    },
    {
      id: "run-8399",
      name: "Instrument master sync",
      detail: "Sample instruments only",
      status: "Pending",
      updated: "04:45 IST",
      owner: "Scheduler",
      value: 0,
    },
  ],
  smtp: [
    {
      id: "mail-201",
      name: "Daily brief · sample user A",
      detail: "sample-a@example.test · report delivery",
      status: "Sent",
      updated: "09:15 IST",
      owner: "Primary sample relay",
      value: 0.8,
    },
    {
      id: "mail-202",
      name: "Daily brief · sample user B",
      detail: "sample-b@example.test · report delivery",
      status: "Queued",
      updated: "09:12 IST",
      owner: "Primary sample relay",
      value: 0,
    },
    {
      id: "mail-203",
      name: "Account notice · sample user C",
      detail: "sample-c@example.test · preview notice",
      status: "Failed",
      updated: "08:57 IST",
      owner: "Fallback sample relay",
      value: 1.4,
    },
  ],
  jobs: [
    {
      id: "daily-brief",
      name: "Daily brief assembly",
      detail: "5:10 IST · research",
      status: "Enabled",
      updated: "Today 05:10",
      owner: "Scheduler",
      value: 4.2,
    },
    {
      id: "score-news",
      name: "Score sample news",
      detail: "Every 30 minutes",
      status: "Enabled",
      updated: "Today 05:00",
      owner: "Worker A",
      value: 1.8,
    },
    {
      id: "refresh-company",
      name: "Refresh company directory",
      detail: "Weekdays · 06:00 IST",
      status: "Paused",
      updated: "Yesterday",
      owner: "Scheduler",
      value: 0,
    },
  ],
  runs: [
    {
      id: "8401",
      name: "Daily brief assembly",
      detail: "run-8401 · sample task",
      status: "Completed",
      updated: "12 Jan 2026 05:10",
      owner: "Scheduler",
      value: 4.2,
    },
    {
      id: "8400",
      name: "Feed ingestion",
      detail: "run-8400 · sample task",
      status: "Completed",
      updated: "12 Jan 2026 05:02",
      owner: "Worker A",
      value: 2.8,
    },
    {
      id: "8399",
      name: "Company directory refresh",
      detail: "run-8399 · sample task",
      status: "Failed",
      updated: "11 Jan 2026 06:00",
      owner: "Worker B",
      value: 18.4,
    },
  ],
  schedule: [
    {
      id: "sch-1",
      name: "Morning brief",
      detail: "Weekdays · 05:10 IST",
      status: "Enabled",
      updated: "Next: 13 Jan 2026",
      owner: "Asia/Kolkata",
      value: 5.1,
    },
    {
      id: "sch-2",
      name: "News refresh",
      detail: "Every 30 minutes",
      status: "Enabled",
      updated: "Next: 12:00 IST",
      owner: "Asia/Kolkata",
      value: 30,
    },
    {
      id: "sch-3",
      name: "Company sync",
      detail: "Weekdays · 06:00 IST",
      status: "Paused",
      updated: "Paused by staff",
      owner: "Asia/Kolkata",
      value: 6,
    },
  ],
  users: [
    {
      id: "u-1001",
      name: "Sample Analyst A",
      detail: "analyst-a@example.test",
      status: "Active",
      updated: "12 Jan 2026",
      owner: "Research desk",
      value: 6,
    },
    {
      id: "u-1002",
      name: "Sample Analyst B",
      detail: "analyst-b@example.test",
      status: "Pending",
      updated: "11 Jan 2026",
      owner: "Independent",
      value: 3,
    },
    {
      id: "u-1003",
      name: "Sample Operator",
      detail: "operator@example.test",
      status: "Active",
      updated: "10 Jan 2026",
      owner: "Sample org",
      value: 7,
    },
  ],
  invites: [
    {
      id: "inv-101",
      name: "Invite · SAMPLE-A1",
      detail: "Single use · expires 20 Jan",
      status: "Pending",
      updated: "12 Jan 2026",
      owner: "Sample Operator",
      value: 1,
    },
    {
      id: "inv-102",
      name: "Invite · SAMPLE-B2",
      detail: "Single use · expires 18 Jan",
      status: "Completed",
      updated: "10 Jan 2026",
      owner: "Sample Operator",
      value: 0,
    },
  ],
  subscriptions: [
    {
      id: "sub-1",
      name: "Sample Research plan",
      detail: "analyst-a@example.test",
      status: "Active",
      updated: "Renews 01 Feb 2026",
      owner: "Annual",
      value: 12,
    },
    {
      id: "sub-2",
      name: "Sample Research plan",
      detail: "analyst-b@example.test",
      status: "Pending",
      updated: "Ends 31 Jan 2026",
      owner: "Monthly",
      value: 1,
    },
  ],
  logins: [
    {
      id: "login-501",
      name: "analyst-a@example.test",
      detail: "Session · browser",
      status: "Active",
      updated: "12 Jan 2026 09:14",
      owner: "Sample IP range",
      value: 0,
    },
    {
      id: "login-502",
      name: "analyst-b@example.test",
      detail: "Failed sign-in",
      status: "Locked",
      updated: "12 Jan 2026 08:52",
      owner: "Sample IP range",
      value: 5,
    },
  ],
  audit: [
    {
      id: "audit-701",
      name: "Updated sample feed settings",
      detail: "Configuration · read-only preview",
      status: "Completed",
      updated: "12 Jan 2026 09:14",
      owner: "Sample Operator",
      value: 1,
    },
    {
      id: "audit-700",
      name: "Generated sample invite",
      detail: "Access · single-use token",
      status: "Completed",
      updated: "12 Jan 2026 08:42",
      owner: "Sample Operator",
      value: 1,
    },
  ],
  feeds: [
    {
      id: "feed-1",
      name: "Sample exchange notices",
      detail: "Source group · market notices",
      status: "Healthy",
      updated: "12 Jan 2026 09:15",
      owner: "Sample parser",
      value: 12,
    },
    {
      id: "feed-2",
      name: "Sample business wires",
      detail: "Source group · business news",
      status: "Pending",
      updated: "12 Jan 2026 09:05",
      owner: "Sample parser",
      value: 3,
    },
    {
      id: "feed-3",
      name: "Sample filings",
      detail: "Source group · company filings",
      status: "Failed",
      updated: "12 Jan 2026 08:45",
      owner: "Sample parser",
      value: 0,
    },
  ],
  instruments: [
    {
      id: "INS-001",
      name: "Sample Index 50",
      detail: "SIMPL50 · Cash index",
      status: "Enabled",
      updated: "12 Jan 2026",
      owner: "Sample exchange",
      value: 24311.2,
    },
    {
      id: "INS-002",
      name: "Acme Industries",
      detail: "ACMEIND · Equity",
      status: "Enabled",
      updated: "12 Jan 2026",
      owner: "Sample exchange",
      value: 1284.5,
    },
    {
      id: "INS-003",
      name: "Bluefin Bank",
      detail: "BLUEBANK · Equity",
      status: "Disabled",
      updated: "11 Jan 2026",
      owner: "Sample exchange",
      value: 842.1,
    },
  ],
  backups: [
    {
      id: "bkp-1",
      name: "Database snapshot",
      detail: "Encrypted · sample backup",
      status: "Completed",
      updated: "12 Jan 2026 02:00",
      owner: "Automated",
      value: 128,
    },
    {
      id: "bkp-2",
      name: "Media archive",
      detail: "Encrypted · sample backup",
      status: "Completed",
      updated: "11 Jan 2026 02:00",
      owner: "Automated",
      value: 84,
    },
  ],
  config: [
    {
      id: "cfg-1",
      name: "Application",
      detail: "Display and runtime options",
      status: "Enabled",
      updated: "12 Jan 2026",
      owner: "Settings",
      value: 6,
    },
    {
      id: "cfg-2",
      name: "Delivery",
      detail: "Email and chat delivery",
      status: "Enabled",
      updated: "12 Jan 2026",
      owner: "Settings",
      value: 4,
    },
    {
      id: "cfg-3",
      name: "Market data",
      detail: "Sample source configuration",
      status: "Pending",
      updated: "11 Jan 2026",
      owner: "Settings",
      value: 3,
    },
  ],
  metrics: [
    {
      id: "metric-1",
      name: "Worker throughput",
      detail: "Across sample worker nodes",
      status: "Healthy",
      updated: "Live · 10s",
      owner: "Jobs",
      value: 1240,
    },
    {
      id: "metric-2",
      name: "Queue depth",
      detail: "Pending sample tasks",
      status: "Healthy",
      updated: "Live · 10s",
      owner: "Queue",
      value: 14,
    },
    {
      id: "metric-3",
      name: "Feed latency",
      detail: "Median source response",
      status: "Pending",
      updated: "Live · 10s",
      owner: "Feeds",
      value: 82,
    },
  ],
  logs: [
    {
      id: "log-301",
      name: "Sample worker ready",
      detail: "INFO · worker-a · task queue connected",
      status: "Healthy",
      updated: "09:15:12 IST",
      owner: "worker-a",
      value: 0,
    },
    {
      id: "log-300",
      name: "Feed retry scheduled",
      detail: "WARN · sample source · retry in 45s",
      status: "Pending",
      updated: "09:14:48 IST",
      owner: "feed-runner",
      value: 1,
    },
    {
      id: "log-299",
      name: "Report export complete",
      detail: "INFO · sample output · 0.8s",
      status: "Completed",
      updated: "09:14:03 IST",
      owner: "worker-b",
      value: 0,
    },
  ],
};

const labels: Record<string, string> = Object.fromEntries(pages.map((p) => [p.key, p.label]));
const descriptions: Record<string, string> = {
  overview: "System health, recent activity and quick operations.",
  jobs: "Inspect scheduled jobs, queues and run history.",
  runs: "Review task status, duration and completion details.",
  logs: "Search the sample application log stream.",
  smtp: "Review mock outbound delivery, relay health and queue status.",
  metrics: "Monitor illustrative worker, queue and source metrics.",
  schedule: "Review sample recurring jobs and their next run times.",
  users: "Manage sample user accounts and feature access.",
  invites: "Create and review fictional invite codes.",
  subscriptions: "Review mock subscription states and renewal dates.",
  logins: "Inspect sample sessions and sign-in lockouts.",
  audit: "Browse the append-only sample administrative activity log.",
  feeds: "Monitor sample ingestion sources and health.",
  instruments: "Review the placeholder market instrument master.",
  config: "Browse grouped application settings without exposing secrets.",
  backups: "Review fictional backup jobs and retention status.",
};

function tone(status: string): Tone {
  return statuses[status] ?? "neutral";
}

function routeFor(path: string): { key: string; detail?: string } {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] !== "ops") return { key: "overview" };
  if (parts[1] === "runs" && parts[2]) return { key: "run-detail", detail: parts[2] };
  if (parts[1] === "users" && parts[2]) return { key: "user-detail", detail: parts[2] };
  if (parts[1] === "audit" && parts[2]) return { key: "audit-detail", detail: parts[2] };
  if (parts[1] === "jobs" && parts[2]) return { key: "job-detail", detail: parts[2] };
  if (parts[1] === "settings" && parts[2]) return { key: "settings-detail", detail: parts[2] };
  return { key: parts[1] || "overview" };
}

function contextualRows(key: string, detail?: string): OpsRow[] {
  if (key === "run-detail") {
    return [
      {
        id: "step-1",
        name: "Initialize task",
        detail: "Worker accepted the sample task.",
        status: "Completed",
        updated: "05:10:00 IST",
        owner: "worker-a",
        value: 0.2,
      },
      {
        id: "step-2",
        name: "Process sample inputs",
        detail: "Processed fictional test fixtures.",
        status: "Completed",
        updated: "05:10:02 IST",
        owner: "worker-a",
        value: 2.7,
      },
      {
        id: "step-3",
        name: "Write sample output",
        detail: "Stored preview result in memory.",
        status: "Completed",
        updated: "05:10:04 IST",
        owner: "worker-a",
        value: 1.3,
      },
    ];
  }
  if (key === "user-detail") {
    return [
      {
        id: "access-1",
        name: "Reports",
        detail: "Daily report archive",
        status: "Enabled",
        updated: "12 Jan 2026",
        owner: "Feature access",
        value: 1,
      },
      {
        id: "access-2",
        name: "News",
        detail: "Scored news feed",
        status: "Enabled",
        updated: "12 Jan 2026",
        owner: "Feature access",
        value: 1,
      },
      {
        id: "access-3",
        name: "Markets",
        detail: "Track record and quotes",
        status: "Pending",
        updated: "12 Jan 2026",
        owner: "Feature access",
        value: 0,
      },
    ];
  }
  if (key === "audit-detail") {
    return [
      {
        id: "event",
        name: "Sample change record",
        detail: "Field values are redacted placeholder content.",
        status: "Completed",
        updated: "12 Jan 2026 09:14",
        owner: "Sample Operator",
        value: 1,
      },
    ];
  }
  if (key === "job-detail") {
    return [
      {
        id: "job-config",
        name: "Schedule",
        detail: "Weekdays at 05:10 IST",
        status: "Enabled",
        updated: "Next run 13 Jan",
        owner: "Asia/Kolkata",
        value: 5.1,
      },
      {
        id: "job-recent",
        name: "Latest sample run",
        detail: "Completed in 4.2 seconds",
        status: "Completed",
        updated: "12 Jan 2026 05:10",
        owner: "worker-a",
        value: 4.2,
      },
    ];
  }
  if (key === "settings-detail") {
    return [
      {
        id: "setting-a",
        name: `${detail ?? "General"} preview option`,
        detail: "Sample value · no secrets shown",
        status: "Enabled",
        updated: "12 Jan 2026",
        owner: "Configuration",
        value: 1,
      },
      {
        id: "setting-b",
        name: "Notification mode",
        detail: "Preview configuration only",
        status: "Pending",
        updated: "12 Jan 2026",
        owner: "Configuration",
        value: 0,
      },
    ];
  }
  return seedRows[key] ?? [];
}

function tableColumns(key: string): Column<OpsRow>[] {
  const isLogs = key === "logs";
  const isUsers = key === "users";
  const isNumeric =
    key === "metrics" || key === "instruments" || key === "overview" || key === "runs";
  return [
    {
      key: "name",
      header: isLogs ? "Event" : isUsers ? "Account" : "Name",
      sortValue: (r) => r.name,
      render: (r) => (
        <Stack gap={0}>
          <Text size="sm" fw={500}>
            {r.name}
          </Text>
          <Text size="xs" c="dimmed">
            {r.detail}
          </Text>
        </Stack>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (r) => r.status,
      render: (r) => <StatusBadge tone={tone(r.status)}>{r.status}</StatusBadge>,
    },
    {
      key: "owner",
      header: isUsers ? "Organization" : isLogs ? "Process" : "Owner",
      hideOnMobile: true,
      render: (r) => r.owner,
    },
    {
      key: "updated",
      header: isLogs ? "Time" : "Updated",
      sortValue: (r) => r.updated,
      render: (r) => (
        <Text size="xs" className="kv2-num">
          {r.updated}
        </Text>
      ),
    },
    {
      key: "value",
      header: isNumeric ? "Value" : "Duration / uses",
      align: "right",
      sortValue: (r) => r.value,
      render: (r) => (
        <Text size="xs" ta="right" className="kv2-num">
          {r.value ? `${r.value}${key === "metrics" ? "" : key === "instruments" ? "" : "s"}` : "—"}
        </Text>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (r) => (
        <Menu position="bottom-end">
          <Menu.Target>
            <ActionIcon aria-label={`Actions for ${r.name}`} variant="subtle">
              <LuEllipsis />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            {key === "runs" || key === "overview" ? (
              <Menu.Item component={AppLink} href={`/v2/ops/runs/${r.id.replace("run-", "")}/`}>
                View run
              </Menu.Item>
            ) : key === "users" ? (
              <Menu.Item component={AppLink} href={`/v2/ops/users/${r.id.replace("u-", "")}/`}>
                View account
              </Menu.Item>
            ) : key === "jobs" ? (
              <Menu.Item component={AppLink} href={`/v2/ops/jobs/${r.id}/`}>
                View job
              </Menu.Item>
            ) : key === "audit" ? (
              <Menu.Item component={AppLink} href={`/v2/ops/audit/${r.id.replace("audit-", "")}/`}>
                View event
              </Menu.Item>
            ) : (
              <Menu.Item
                onClick={() =>
                  notifications.show({
                    title: "Preview only",
                    message: "No changes are made in this mock page.",
                  })
                }
              >
                View details
              </Menu.Item>
            )}
          </Menu.Dropdown>
        </Menu>
      ),
    },
  ];
}

function showPreviewToast(title: string) {
  notifications.show({
    title,
    message: "This is a mock preview. No system data or settings were changed.",
  });
}

function OpsNavigation({ active }: { active: string }) {
  return (
    <Group gap={6} mb="md" style={{ overflowX: "auto", flexWrap: "nowrap" }}>
      {pages.map((item) => (
        <Button
          key={item.key}
          component={AppLink}
          href={item.path}
          variant={active === item.key ? "light" : "subtle"}
          color={active === item.key ? "indigo" : "slate"}
          size="xs"
          style={{ flex: "0 0 auto" }}
        >
          {item.label}
        </Button>
      ))}
    </Group>
  );
}

/** All v2 operations surfaces use sample-only data. `path` is the route splat below `/v2/ops/`. */
export function OpsPage({ path = "ops/" }: { path?: string }) {
  const { key: routeKey, detail } = routeFor(path);
  const key = [
    "run-detail",
    "user-detail",
    "audit-detail",
    "job-detail",
    "settings-detail",
  ].includes(routeKey)
    ? routeKey
    : routeKey;
  const navKey =
    key === "run-detail"
      ? "runs"
      : key === "user-detail"
        ? "users"
        : key === "audit-detail"
          ? "audit"
          : key === "job-detail"
            ? "jobs"
            : key === "settings-detail"
              ? "config"
              : key;
  const pageTitle =
    key === "run-detail"
      ? `Task run ${detail}`
      : key === "user-detail"
        ? `Sample user ${detail}`
        : key === "audit-detail"
          ? `Audit event ${detail}`
          : key === "job-detail"
            ? "Daily brief assembly"
            : key === "settings-detail"
              ? `${(detail ?? "General").replace(/^\w/, (c) => c.toUpperCase())} settings`
              : (labels[key] ?? "Operations");
  const rows = useMemo(() => contextualRows(key, detail), [key, detail]);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("All");
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!query ||
            `${row.name} ${row.detail} ${row.owner} ${row.id}`
              .toLowerCase()
              .includes(query.toLowerCase())) &&
          (state === "All" || row.status === state),
      ),
    [rows, query, state],
  );
  const isDetail = key.endsWith("-detail");

  const actions = (
    <>
      <Button
        variant="default"
        leftSection={<LuRefreshCw size={14} />}
        onClick={() => showPreviewToast("Preview refreshed")}
      >
        Refresh
      </Button>
      {key === "jobs" || key === "job-detail" ? (
        <Button
          leftSection={<LuPlay size={14} />}
          onClick={() => showPreviewToast("Sample job queued")}
        >
          Run job
        </Button>
      ) : key === "invites" ? (
        <Button
          leftSection={<LuFilePlus2 size={14} />}
          onClick={() =>
            modals.openConfirmModal({
              title: "Create a sample invite",
              children: (
                <Stack gap={8}>
                  <Text size="sm">
                    This creates no real invitation. The code below is a fictional example.
                  </Text>
                  <Code>SAMPLE-INVITE-2026</Code>
                  <Text size="xs" c="dimmed">
                    Single use · expires in 7 days
                  </Text>
                </Stack>
              ),
              labels: { confirm: "Preview invite", cancel: "Cancel" },
              onConfirm: () => showPreviewToast("Sample invite previewed"),
            })
          }
        >
          Create invite
        </Button>
      ) : key === "schedule" ? (
        <Button
          leftSection={<LuFilePlus2 size={14} />}
          onClick={() => showPreviewToast("Schedule editor opened")}
        >
          Add schedule
        </Button>
      ) : key === "backups" ? (
        <Button
          leftSection={<LuPlay size={14} />}
          onClick={() =>
            modals.openConfirmModal({
              title: "Run sample backup?",
              children: (
                <Text size="sm">This preview will not create or restore a real backup.</Text>
              ),
              labels: { confirm: "Run preview", cancel: "Cancel" },
              onConfirm: () => showPreviewToast("Preview backup queued"),
            })
          }
        >
          Run backup
        </Button>
      ) : null}

      {key === "smtp" ? (
        <Stack gap={12} mb={12}>
          <KpiGrid cols={4}>
            <KpiTile label="Queue depth" value="2" hint="Sample messages pending" />
            <KpiTile
              label="Primary relay"
              value={<StatusBadge tone="gain">Healthy</StatusBadge>}
              hint="Fictional relay state"
            />
            <KpiTile
              label="Fallback relay"
              value={<StatusBadge tone="info">Ready</StatusBadge>}
              hint="Not connected to a service"
            />
            <KpiTile label="Delivered today" value="126" hint="Placeholder count" />
          </KpiGrid>
          <Panel
            title="Relay controls"
            info="Failover and restore actions are simulated; no email is sent."
          >
            <Group gap={8} wrap="wrap">
              <Button
                color="amber"
                onClick={() =>
                  modals.openConfirmModal({
                    title: "Switch to sample fallback?",
                    children: (
                      <Text size="sm">
                        Preview only. This will not change a real relay or send messages.
                      </Text>
                    ),
                    labels: { confirm: "Preview switch", cancel: "Cancel" },
                    onConfirm: () => showPreviewToast("Sample failover previewed"),
                  })
                }
              >
                Switch to fallback
              </Button>
              <Button
                variant="default"
                onClick={() =>
                  modals.openConfirmModal({
                    title: "Restore sample primary relay?",
                    children: (
                      <Text size="sm">Preview only. No live relay configuration is changed.</Text>
                    ),
                    labels: { confirm: "Preview restore", cancel: "Cancel" },
                    onConfirm: () => showPreviewToast("Sample restore previewed"),
                  })
                }
              >
                Restore primary
              </Button>
              <Text size="xs" c="dimmed">
                Current state: primary active · 0 sample retries
              </Text>
            </Group>
          </Panel>
        </Stack>
      ) : null}
    </>
  );

  return (
    <Page>
      <PageHeader
        title={pageTitle}
        crumbs={
          isDetail
            ? [
                { label: "Operations", to: "/v2/ops/" },
                {
                  label: labels[navKey] ?? "Operations",
                  to: pages.find((p) => p.key === navKey)?.path,
                },
                { label: detail ?? "Detail" },
              ]
            : undefined
        }
        description={
          descriptions[key] ?? "Review a sample operations record. All data is fictional."
        }
        meta={
          <StatusBadge tone="caution" dot>
            Preview only
          </StatusBadge>
        }
        actions={actions}
      />
      <OpsNavigation active={navKey} />

      {key === "overview" ? (
        <Stack gap={12} mb={12}>
          <Panel
            title="System health"
            info="All metrics and service names on this page are fictional placeholders for design review."
            actions={
              <StatusBadge tone="gain" dot pulse>
                All sample checks passing
              </StatusBadge>
            }
          >
            <KpiGrid cols={4}>
              <KpiTile label="Services" value="6 / 6" hint="Sample components healthy" />
              <KpiTile
                label="Queue depth"
                value="14"
                hint="Illustrative tasks"
                info="A real queue count will be connected later."
              />
              <KpiTile label="Worker latency" value="14 ms" hint="Sample median" />
              <KpiTile label="Uptime" value="99.9%" hint="Mock rolling period" />
            </KpiGrid>
          </Panel>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing={12}>
            <Panel title="Infrastructure & pipeline">
              <Stack gap={12}>
                {["Database", "Task queue", "News ingestion", "Report delivery"].map(
                  (item, index) => (
                    <Group key={item} justify="space-between">
                      <Group gap={8}>
                        <LuCircleCheck size={15} color="var(--kv2-gain)" />
                        <Text size="sm">{item}</Text>
                      </Group>
                      <StatusBadge tone={index === 3 ? "caution" : "gain"}>
                        {index === 3 ? "Sample delay" : "Healthy"}
                      </StatusBadge>
                    </Group>
                  ),
                )}
              </Stack>
            </Panel>
            <Panel title="Worker throughput" info="Illustrative event rate, not live telemetry.">
              <Stack gap={12}>
                <Group justify="space-between">
                  <Text size="sm">Sample tasks / minute</Text>
                  <Text fw={600} className="kv2-num">
                    1,240
                  </Text>
                </Group>
                <Progress value={64} color="indigo.6" size="sm" />
                <Group justify="space-between">
                  <Text size="xs" c="dimmed">
                    Peak utilization · 4 sample workers
                  </Text>
                  <Delta value={2.4} />
                </Group>
                <div style={{ height: 48 }}>
                  <svg
                    viewBox="0 0 300 48"
                    width="100%"
                    height="48"
                    aria-label="Sample throughput trend"
                  >
                    <polyline
                      fill="none"
                      stroke="var(--kv2-brand)"
                      strokeWidth="2"
                      points={mockSeries(20, 20, 71, 0.02)
                        .map((v, i) => `${i * 15},${44 - v}`)
                        .join(" ")}
                    />
                  </svg>
                </div>
              </Stack>
            </Panel>
          </SimpleGrid>
        </Stack>
      ) : null}

      {key === "metrics" ? (
        <KpiGrid cols={4}>
          <KpiTile
            label="CPU use"
            value="28.4%"
            hint="4 sample nodes"
            info="Placeholder telemetry for layout review."
          />
          <KpiTile label="Memory" value="62.1%" hint="Sample average" />
          <KpiTile label="Queue throughput" value="1,240/min" hint="Mock rolling rate" />
          <KpiTile label="Source latency" value="82 ms" hint="Mock median" />
        </KpiGrid>
      ) : null}

      {key === "run-detail" ||
      key === "job-detail" ||
      key === "user-detail" ||
      key === "audit-detail" ||
      key === "settings-detail" ? (
        <Stack gap={12} mb={12}>
          <Panel
            title={
              key === "run-detail"
                ? "Run summary"
                : key === "user-detail"
                  ? "Account summary"
                  : key === "audit-detail"
                    ? "Event summary"
                    : key === "settings-detail"
                      ? "Configuration group"
                      : "Job summary"
            }
          >
            {key === "run-detail" ? (
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
                <KpiTile
                  label="Status"
                  value={<StatusBadge tone="gain">Completed</StatusBadge>}
                  hint="Sample run"
                />
                <KpiTile label="Duration" value="4.2 s" hint="Illustrative timing" />
                <KpiTile label="Started by" value="Scheduler" hint="Sample trigger" />
                <KpiTile label="Worker" value="worker-a" hint="Placeholder node" />
              </SimpleGrid>
            ) : key === "user-detail" ? (
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
                <KpiTile label="Account" value="Active" hint="Sample state" />
                <KpiTile label="Email" value="sample@example.test" hint="Not a real user" />
                <KpiTile label="Subscription" value="Research" hint="Mock plan" />
                <KpiTile label="Sessions" value="2" hint="Sample sessions" />
              </SimpleGrid>
            ) : (
              <Text size="sm" c="dimmed">
                {key === "audit-detail"
                  ? "Fictional audit entry; identifying details and payload values are omitted."
                  : key === "settings-detail"
                    ? "Settings shown here are placeholders. Secrets and environment values are never displayed."
                    : "Sample job configuration and recent execution."}
              </Text>
            )}
          </Panel>
          {key === "user-detail" ? (
            <Tabs defaultValue="access">
              <Tabs.List>
                <Tabs.Tab value="access">Feature access</Tabs.Tab>
                <Tabs.Tab value="activity">Activity</Tabs.Tab>
                <Tabs.Tab value="sessions">Sessions</Tabs.Tab>
                <Tabs.Tab value="subscription">Subscription</Tabs.Tab>
              </Tabs.List>
              {["access", "activity", "sessions", "subscription"].map((tab) => (
                <Tabs.Panel key={tab} value={tab} pt="sm">
                  <Panel title={tab[0].toUpperCase() + tab.slice(1)}>
                    <Text size="sm" c="dimmed">
                      Fictional {tab} information for this sample user.
                    </Text>
                  </Panel>
                </Tabs.Panel>
              ))}
            </Tabs>
          ) : key === "run-detail" ? (
            <Panel title="Execution timeline">
              <Timeline active={3} bulletSize={18} lineWidth={2}>
                {rows.map((row) => (
                  <Timeline.Item key={row.id} title={row.name}>
                    <Text size="xs" c="dimmed">
                      {row.updated} · {row.detail}
                    </Text>
                  </Timeline.Item>
                ))}
              </Timeline>
            </Panel>
          ) : null}
        </Stack>
      ) : null}

      {key === "logs" ? (
        <Panel
          title="Sample logs"
          actions={
            <Group gap={6}>
              <StatusBadge tone="gain" dot pulse>
                Paused
              </StatusBadge>
              <Button
                size="xs"
                variant="default"
                onClick={() => showPreviewToast("Log stream cleared")}
              >
                Clear
              </Button>
            </Group>
          }
        >
          <Stack gap={10}>
            <AlertLogNotice />
            <Code block className="kv2-terminal">
              {rows
                .map(
                  (r) =>
                    `${r.updated}  ${r.status.toUpperCase().padEnd(9)}  ${r.owner}  ${r.detail}`,
                )
                .join("\n")}
            </Code>
          </Stack>
        </Panel>
      ) : null}

      {key === "schedule" ? (
        <Panel
          title="Schedule calendar"
          info="All times use IST. The schedule shown is illustrative."
        >
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            {rows.map((r) => (
              <Panel
                key={r.id}
                title={r.name}
                actions={<StatusBadge tone={tone(r.status)}>{r.status}</StatusBadge>}
              >
                <Stack gap={8}>
                  <Text size="sm">{r.detail}</Text>
                  <Text size="xs" c="dimmed">
                    {r.updated}
                  </Text>
                  <Group>
                    <Button
                      size="xs"
                      variant="default"
                      onClick={() => showPreviewToast("Schedule editor opened")}
                    >
                      Edit
                    </Button>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() => showPreviewToast("Preview only")}
                    >
                      Disable
                    </Button>
                  </Group>
                </Stack>
              </Panel>
            ))}
          </SimpleGrid>
        </Panel>
      ) : null}

      {key === "config" ? (
        <Panel title="Settings groups" info="Settings are mock-only and contain no real secrets.">
          <Stack gap={8}>
            {["general", "email", "market-data", "security", "retention"].map((group) => (
              <Group
                key={group}
                justify="space-between"
                p="sm"
                style={{ borderBottom: "1px solid var(--kv2-border)" }}
              >
                <Stack gap={0}>
                  <Text size="sm" fw={500}>
                    {group.replace("-", " ").replace(/^\w/, (c) => c.toUpperCase())}
                  </Text>
                  <Text size="xs" c="dimmed">
                    Sample settings group · no secret values
                  </Text>
                </Stack>
                <Button
                  component={AppLink}
                  href={`/v2/ops/settings/${group}/`}
                  size="xs"
                  variant="default"
                >
                  Open
                </Button>
              </Group>
            ))}
          </Stack>
        </Panel>
      ) : null}

      {key === "backups" ? (
        <Panel
          title="Backup & recovery"
          info="Preview-only records. No restore or backup actions are performed."
        >
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <KpiTile
              label="Latest snapshot"
              value="12 Jan 2026 · 02:00 IST"
              hint="Fictional database backup"
            />
            <KpiTile label="Retention" value="14 days" hint="Mock policy" />
          </SimpleGrid>
        </Panel>
      ) : null}

      {key === "users" || key === "invites" ? (
        <Group justify="space-between" mb={8}>
          <Text size="xs" c="dimmed">
            Showing {filtered.length} of {rows.length} sample records.
          </Text>
          <Button
            size="xs"
            variant="default"
            leftSection={<LuArrowDownToLine size={14} />}
            onClick={() => showPreviewToast("Sample CSV prepared")}
          >
            Export CSV
          </Button>
        </Group>
      ) : null}

      {key === "run-detail" && rows.length === 0 ? <EmptyState title="No run steps" /> : null}
      {key !== "overview" &&
      key !== "metrics" &&
      key !== "schedule" &&
      key !== "config" &&
      key !== "backups" &&
      key !== "logs" ? (
        <Panel
          title={
            key === "runs"
              ? "Recent task runs"
              : key === "jobs"
                ? "Job registry"
                : key === "users"
                  ? "User accounts"
                  : key === "invites"
                    ? "Invite codes"
                    : key === "subscriptions"
                      ? "Subscriptions"
                      : key === "logins"
                        ? "Login activity"
                        : key === "audit"
                          ? "Audit events"
                          : key === "feeds"
                            ? "Ingestion sources"
                            : key === "instruments"
                              ? "Instrument master"
                              : key === "smtp"
                                ? "Outbound message queue"
                                : key === "run-detail"
                                  ? "Run logs"
                                  : key === "job-detail"
                                    ? "Recent executions"
                                    : key === "user-detail"
                                      ? "Feature entitlements"
                                      : key === "audit-detail"
                                        ? "Event payload"
                                        : "Settings"
          }
          info="Rows and values are fictional placeholders for the v2 design preview."
          actions={
            key === "audit" ? (
              <Button
                size="xs"
                variant="default"
                leftSection={<LuArrowDownToLine size={14} />}
                onClick={() => showPreviewToast("Audit CSV prepared")}
              >
                Export audit
              </Button>
            ) : undefined
          }
          flush
        >
          <DataTable
            rows={filtered}
            rowKey={(row) => row.id}
            columns={tableColumns(key)}
            toolbar={
              <Group gap={8} wrap="wrap" style={{ width: "100%" }}>
                <TextInput
                  aria-label="Search operations records"
                  placeholder="Search records…"
                  leftSection={<LuSearch size={14} />}
                  value={query}
                  onChange={(event) => setQuery(event.currentTarget.value)}
                  style={{ flex: "1 1 200px" }}
                />
                <SegmentedControl
                  aria-label="Filter by status"
                  data={["All", ...new Set(rows.map((r) => r.status))]}
                  value={state}
                  onChange={setState}
                />
                <Tooltip label="Filters apply to sample rows">
                  <ActionIcon aria-label="Filter info">
                    <LuFilter />
                  </ActionIcon>
                </Tooltip>
              </Group>
            }
            empty={
              <EmptyState
                title="No matching records"
                description="Try a different search or status filter."
              />
            }
            pageSize={10}
          />
        </Panel>
      ) : null}

      {key === "overview" ? (
        <Panel
          title="Recent activity"
          info="Sample events only; this preview is disconnected from task queues and production data."
          actions={
            <Anchor component={AppLink} href="/v2/ops/runs/" size="xs">
              All runs →
            </Anchor>
          }
          flush
        >
          <DataTable
            rows={rows}
            rowKey={(r) => r.id}
            columns={tableColumns("overview")}
            paginate={false}
          />
        </Panel>
      ) : null}
    </Page>
  );
}

function AlertLogNotice() {
  return (
    <Group gap={8} c="var(--kv2-text-muted)">
      <LuCircleHelp size={14} />
      <Text size="xs">
        Use search to filter events. No live stream is connected in this preview.
      </Text>
      <LuTriangleAlert size={14} />
    </Group>
  );
}
