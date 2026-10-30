import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Collapse,
  Grid,
  Group,
  Modal,
  PinInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import { TimeInput } from "@mantine/dates";
import { notifications } from "@mantine/notifications";
import { useMemo, useState } from "react";
import { LuChevronDown, LuChevronRight, LuMail, LuSend, LuX } from "react-icons/lu";
import type { ReactNode } from "react";

import {
  AppLink,
  EmptyState,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  StatusBadge,
  formatDate,
  formatNumber,
} from "../components";
import type { Tone } from "../components";
import { deliveryLog, profile, telegramSample } from "../mock/account";
import type { ChannelKind, DeliveryAttempt, DeliveryStatus } from "../mock/account";

type ChannelState = "not-connected" | "pending" | "connected";

const statusTone: Record<DeliveryStatus, Tone> = {
  sent: "gain",
  failed: "loss",
  retrying: "caution",
};
const statusLabel: Record<DeliveryStatus, string> = {
  sent: "Sent ✓",
  failed: "Failed ✕",
  retrying: "Retrying",
};
const channelIcon: Record<ChannelKind, ReactNode> = {
  email: <LuMail size={14} />,
  telegram: <LuSend size={14} />,
};
const channelName: Record<ChannelKind, string> = { email: "Email", telegram: "Telegram" };

const contentOptions = [
  { key: "outlook", label: "Index outlook", help: "Next-session direction for each sample index." },
  {
    key: "movers",
    label: "Top movers",
    help: "Biggest gainers and losers from the previous session.",
  },
  { key: "news", label: "Scored news", help: "Top 5 articles by relevance with sentiment scores." },
  { key: "ipos", label: "IPO updates", help: "Open and upcoming sample IPOs with scores." },
  {
    key: "review",
    label: "Prediction review",
    help: "How yesterday's outlook compared with the result.",
  },
];

function ChannelRow({
  icon,
  name,
  detail,
  state,
  enabled,
  onToggle,
  action,
  children,
}: {
  icon: ReactNode;
  name: string;
  detail: ReactNode;
  state: ChannelState;
  enabled: boolean;
  onToggle: (value: boolean) => void;
  action: ReactNode;
  children?: ReactNode;
}) {
  const badge =
    state === "connected" ? (
      <StatusBadge tone="gain" dot size="xs">
        Connected
      </StatusBadge>
    ) : state === "pending" ? (
      <StatusBadge tone="caution" dot size="xs">
        Waiting for verification
      </StatusBadge>
    ) : (
      <StatusBadge tone="neutral" size="xs">
        Not connected
      </StatusBadge>
    );
  return (
    <Stack gap={10} py={12} style={{ borderBottom: "1px solid var(--kv2-border)" }}>
      <Group justify="space-between" wrap="wrap" gap={10}>
        <Group gap={10} wrap="nowrap" style={{ minWidth: 0 }}>
          <span className="kv2-state-icon" style={{ margin: 0 }}>
            {icon}
          </span>
          <Stack gap={2} style={{ minWidth: 0 }}>
            <Group gap={6}>
              <Text size="sm" fw={600}>
                {name}
              </Text>
              {badge}
            </Group>
            <Text size="xs" c="dimmed">
              {detail}
            </Text>
          </Stack>
        </Group>
        <Group gap={10}>
          {action}
          <Switch
            aria-label={`Send reports by ${name}`}
            checked={enabled}
            disabled={state !== "connected"}
            onChange={(e) => onToggle(e.currentTarget.checked)}
            label="Send reports"
          />
        </Group>
      </Group>
      {children}
    </Stack>
  );
}

type Batch = { date: string; report: string; attempts: DeliveryAttempt[] };

export function DeliveryPage() {
  const [emailState, setEmailState] = useState<ChannelState>(
    profile.emailVerified ? "connected" : "pending",
  );
  const [telegramState, setTelegramState] = useState<ChannelState>("connected");
  const [emailOn, setEmailOn] = useState(false);
  const [telegramOn, setTelegramOn] = useState(true);
  const [code, setCode] = useState("");
  const [linkOpen, setLinkOpen] = useState(false);
  const [time, setTime] = useState("08:00");
  const [days, setDays] = useState<string | null>("trading");
  const [content, setContent] = useState<string[]>(["outlook", "movers", "news"]);
  const [channelFilter, setChannelFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ "2026-01-12": true });

  const saved = (message: string) =>
    notifications.show({ title: "Saved", message, color: "emerald" });

  const filteredLog = deliveryLog.filter(
    (a) =>
      (!channelFilter || a.channel === channelFilter) &&
      (!statusFilter || a.status === statusFilter),
  );
  const batches = useMemo(() => {
    const map = new Map<string, Batch>();
    for (const a of filteredLog) {
      const key = a.report === "Test" ? `test-${a.id}` : a.date;
      if (!map.has(key)) map.set(key, { date: a.date, report: a.report, attempts: [] });
      map.get(key)?.attempts.push(a);
    }
    return [...map.entries()];
  }, [filteredLog]);

  const reportAttempts = deliveryLog.filter((a) => a.report !== "Test");
  const sentCount = reportAttempts.filter((a) => a.status === "sent").length;
  const successRate = (sentCount / reportAttempts.length) * 100;
  const configured = [emailState, telegramState].filter((s) => s === "connected").length;
  const anyEnabled =
    (emailOn && emailState === "connected") || (telegramOn && telegramState === "connected");

  const sendTest = () => {
    if (!anyEnabled) {
      notifications.show({
        title: "No channel enabled",
        message: "Connect a channel and turn on “Send reports” first.",
        color: "amber",
      });
      return;
    }
    notifications.show({
      title: "Test message sent",
      message: `A sample brief was sent to ${[emailOn && emailState === "connected" ? "email" : null, telegramOn && telegramState === "connected" ? "Telegram" : null].filter(Boolean).join(" and ")}.`,
      color: "emerald",
    });
  };

  return (
    <Page>
      <PageHeader
        title="Delivery"
        crumbs={[{ label: "Kash Engine", to: "/v2/" }, { label: "Delivery" }]}
        description="Choose where the daily brief is sent, when, and what it contains. Check below whether each report reached every channel."
        actions={
          <Button leftSection={<LuSend size={14} />} onClick={sendTest}>
            Send test
          </Button>
        }
      />

      <Stack gap={16}>
        <KpiGrid cols={4}>
          <KpiTile
            label="Last delivery"
            value="12 Jan, 08:01 IST"
            hint="Morning brief · 2 of 2 sent"
          />
          <KpiTile
            label="7-day success rate"
            info="Share of report deliveries (excluding tests) that reached the channel on the first or a retried attempt."
            value={`${formatNumber(successRate, 1)}%`}
            hint={`${sentCount} / ${reportAttempts.length} sent`}
          />
          <KpiTile
            label="Channels configured"
            value={`${configured} of 2`}
            hint="Email, Telegram"
          />
          <KpiTile
            label="Next brief"
            value={`Tomorrow, ${time || "—"} IST`}
            hint={days === "trading" ? "Trading days only" : "Every day"}
          />
        </KpiGrid>

        <Grid gutter={16}>
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Panel
              title="Channels"
              info="Switches save instantly. A channel must be verified before reports can be sent to it."
            >
              <Stack gap={0} mt={-12}>
                <ChannelRow
                  icon={<LuMail size={16} />}
                  name="Email"
                  state={emailState}
                  enabled={emailOn}
                  onToggle={(v) => {
                    setEmailOn(v);
                    saved(v ? "Email reports turned on." : "Email reports turned off.");
                  }}
                  detail={
                    emailState === "connected"
                      ? `Reports go to ${profile.email}`
                      : `Verify ${profile.email} to receive reports by email.`
                  }
                  action={
                    emailState !== "connected" ? (
                      <Button
                        size="xs"
                        variant="default"
                        onClick={() =>
                          notifications.show({
                            title: "Verification email sent",
                            message: `Check ${profile.email} for a 6-digit code (sample: any 6 digits).`,
                          })
                        }
                      >
                        Send verification email
                      </Button>
                    ) : null
                  }
                >
                  {emailState === "pending" ? (
                    <Group gap={8} pl={42} wrap="wrap">
                      <PinInput
                        length={6}
                        size="xs"
                        type="number"
                        value={code}
                        onChange={setCode}
                        aria-label="Code"
                      />
                      <Button
                        size="xs"
                        disabled={code.length !== 6}
                        onClick={() => {
                          setEmailState("connected");
                          setEmailOn(true);
                          saved("Email verified. Reports will be sent by email.");
                        }}
                      >
                        Verify
                      </Button>
                    </Group>
                  ) : null}
                </ChannelRow>
                <ChannelRow
                  icon={<LuSend size={16} />}
                  name="Telegram"
                  state={telegramState}
                  enabled={telegramOn}
                  onToggle={(v) => {
                    setTelegramOn(v);
                    saved(v ? "Telegram reports turned on." : "Telegram reports turned off.");
                  }}
                  detail={
                    telegramState === "connected"
                      ? `Linked to ${telegramSample.chat} via ${telegramSample.handle}`
                      : telegramState === "pending"
                        ? "Open Telegram to finish linking."
                        : "Link a Telegram chat to receive the brief there."
                  }
                  action={
                    telegramState === "connected" ? (
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        onClick={() => {
                          setTelegramState("not-connected");
                          setTelegramOn(false);
                          notifications.show({
                            title: "Telegram disconnected",
                            message: "Reports stop going to Telegram.",
                          });
                        }}
                      >
                        Disconnect
                      </Button>
                    ) : (
                      <Button
                        size="xs"
                        variant="default"
                        onClick={() => {
                          setTelegramState("pending");
                          setLinkOpen(true);
                        }}
                      >
                        {telegramState === "pending" ? "Show link" : "Link Telegram"}
                      </Button>
                    )
                  }
                />
              </Stack>
            </Panel>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap={16}>
              <Panel
                title="Schedule"
                info="Briefs are generated before the market opens. Times are IST."
              >
                <Group grow align="flex-end" wrap="wrap">
                  <TimeInput
                    label="Daily brief time"
                    value={time}
                    onChange={(e) => setTime(e.currentTarget.value)}
                    onBlur={() => saved(`Brief time set to ${time} IST.`)}
                    miw={140}
                  />
                  <Select
                    label="Send on"
                    data={[
                      { value: "trading", label: "Trading days" },
                      { value: "all", label: "Every day" },
                    ]}
                    value={days}
                    onChange={(v) => {
                      setDays(v);
                      saved("Schedule updated.");
                    }}
                    allowDeselect={false}
                    miw={140}
                  />
                </Group>
              </Panel>
              <Panel
                title="Brief content"
                info="Choose sections to include. Applies to every channel."
              >
                <Checkbox.Group
                  value={content}
                  onChange={(v) => {
                    setContent(v);
                    saved(`${v.length} sections in the brief.`);
                  }}
                >
                  <Stack gap={8}>
                    {contentOptions.map((o) => (
                      <Checkbox key={o.key} value={o.key} label={o.label} description={o.help} />
                    ))}
                  </Stack>
                </Checkbox.Group>
              </Panel>
            </Stack>
          </Grid.Col>
        </Grid>

        <Panel
          flush
          title="Delivery log"
          info="Newest first, grouped by report date. Expand a report to see each channel."
          actions={
            <Text size="xs" c="dimmed">
              Last 7 days
            </Text>
          }
        >
          <div className="kv2-toolbar">
            <Group gap={8} w="100%" wrap="wrap">
              <Select
                aria-label="Channel"
                placeholder="All channels"
                data={[
                  { value: "email", label: "Email" },
                  { value: "telegram", label: "Telegram" },
                ]}
                value={channelFilter}
                onChange={setChannelFilter}
                clearable
                w={{ base: "100%", sm: 160 }}
              />
              <Select
                aria-label="Status"
                placeholder="All statuses"
                data={[
                  { value: "sent", label: "Sent" },
                  { value: "failed", label: "Failed" },
                  { value: "retrying", label: "Retrying" },
                ]}
                value={statusFilter}
                onChange={setStatusFilter}
                clearable
                w={{ base: "100%", sm: 160 }}
              />
              {channelFilter || statusFilter ? (
                <Button
                  variant="subtle"
                  leftSection={<LuX size={14} />}
                  onClick={() => {
                    setChannelFilter(null);
                    setStatusFilter(null);
                  }}
                >
                  Clear
                </Button>
              ) : null}
              <Text size="xs" c="dimmed" ml="auto">
                {filteredLog.length} attempts
              </Text>
            </Group>
          </div>
          {batches.length === 0 ? (
            <EmptyState title="No attempts match" description="Try another channel or status." />
          ) : (
            <div className="kv2-table-wrap">
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Report / channel</Table.Th>
                    <Table.Th>Time</Table.Th>
                    <Table.Th>Result</Table.Th>
                    <Table.Th data-align="right" visibleFrom="md">
                      Latency
                    </Table.Th>
                    <Table.Th visibleFrom="md">Details</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {batches.map(([key, batch]) => {
                    const sent = batch.attempts.filter((a) => a.status === "sent").length;
                    const all = sent === batch.attempts.length;
                    const isOpen = open[key] ?? false;
                    return [
                      <Table.Tr key={key} data-clickable="true">
                        <Table.Td colSpan={5} style={{ background: "var(--kv2-surface-muted)" }}>
                          <UnstyledButton
                            onClick={() => setOpen((o) => ({ ...o, [key]: !isOpen }))}
                            aria-expanded={isOpen}
                            w="100%"
                          >
                            <Group gap={8} wrap="wrap">
                              {isOpen ? <LuChevronDown size={14} /> : <LuChevronRight size={14} />}
                              <Text size="sm" fw={600}>
                                {batch.report === "Test"
                                  ? `Test message · ${formatDate(batch.date)}`
                                  : `${formatDate(batch.date)} morning brief`}
                              </Text>
                              <StatusBadge tone={all ? "gain" : "caution"} size="xs">
                                {sent}/{batch.attempts.length} sent {all ? "✓" : ""}
                              </StatusBadge>
                              {batch.report !== "Test" ? (
                                <Anchor
                                  component={AppLink}
                                  href={`/v2/reports/${batch.date}/`}
                                  size="xs"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  Open report
                                </Anchor>
                              ) : null}
                            </Group>
                          </UnstyledButton>
                        </Table.Td>
                      </Table.Tr>,
                      ...(isOpen
                        ? batch.attempts.map((a) => (
                            <Table.Tr key={a.id}>
                              <Table.Td>
                                <Group gap={6} wrap="nowrap" pl={22}>
                                  {channelIcon[a.channel]}
                                  <Text size="sm">{channelName[a.channel]}</Text>
                                  <Text size="xs" c="dimmed" visibleFrom="sm">
                                    {a.target}
                                  </Text>
                                </Group>
                              </Table.Td>
                              <Table.Td className="kv2-num">{a.time} IST</Table.Td>
                              <Table.Td>
                                <StatusBadge tone={statusTone[a.status]} size="xs">
                                  {statusLabel[a.status]}
                                </StatusBadge>
                              </Table.Td>
                              <Table.Td data-align="right" className="kv2-num" visibleFrom="md">
                                {formatNumber(a.latencyMs)} ms
                              </Table.Td>
                              <Table.Td visibleFrom="md">
                                <Text size="xs" c="dimmed">
                                  {a.detail}
                                </Text>
                              </Table.Td>
                            </Table.Tr>
                          ))
                        : []),
                    ];
                  })}
                </Table.Tbody>
              </Table>
            </div>
          )}
        </Panel>
      </Stack>

      <Modal opened={linkOpen} onClose={() => setLinkOpen(false)} title="Link Telegram">
        <Stack gap={12}>
          <Text size="sm">
            Open the sample bot in Telegram and press <b>Start</b>. The link expires in 10 minutes.
          </Text>
          <TextInput
            readOnly
            value="https://example.com/telegram-link/SAMPLE-1234"
            className="kv2-mono"
          />
          <Collapse in={telegramState === "pending"}>
            <Badge color="amber" variant="light">
              Waiting for Telegram…
            </Badge>
          </Collapse>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setLinkOpen(false)}>
              Close
            </Button>
            <Button
              onClick={() => {
                setTelegramState("connected");
                setTelegramOn(true);
                setLinkOpen(false);
                saved("Telegram linked (sample).");
              }}
            >
              I've finished linking
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Page>
  );
}
