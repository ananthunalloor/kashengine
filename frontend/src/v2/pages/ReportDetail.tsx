import {
  Alert,
  Anchor,
  Box,
  Button,
  Collapse,
  Grid,
  Group,
  Menu,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { useClipboard } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { useMemo, useState } from "react";
import {
  LuChevronDown,
  LuChevronLeft,
  LuChevronRight,
  LuChevronUp,
  LuCircleCheck,
  LuCircleX,
  LuCopy,
  LuDownload,
  LuFileText,
  LuLink,
  LuPrinter,
  LuRefreshCw,
  LuShare2,
} from "react-icons/lu";

import {
  AppLink,
  Delta,
  DescriptionList,
  EmptyState,
  InfoTip,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  SentimentPill,
  StatusBadge,
  StrengthMeter,
  SymbolChip,
  formatDate,
  formatNumber,
} from "../components";
import { companies, sampleUser } from "../mock/data";
import { neighbours, outcomeOf, plainText, reportFor } from "../mock/reports";
import type { DailyReport } from "../mock/reports";
import { OutcomeBadge, OutlookBadge } from "./Reports";

const sections = [
  { id: "outlook", label: "Outlook" },
  { id: "index-closes", label: "Index closes" },
  { id: "key-news", label: "Key news" },
  { id: "ipo-watch", label: "IPO watch" },
  { id: "global-cues", label: "Global cues" },
  { id: "delivered-text", label: "Delivered text" },
];

function shortDate(day: string) {
  return formatDate(day).slice(0, 6);
}

function DeliveryPanel({ report }: { report: DailyReport }) {
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(true);
  const sent = report.delivery.filter((d) => d.result === "sent").length;
  const total = report.delivery.length;
  const rows = report.delivery.filter((d) => filter === "all" || d.result === filter);
  const allOk = total > 0 && sent === total;
  return (
    <Panel
      title="Delivery"
      info="Each channel the report was pushed to, when, and what the provider answered. Failed sends are retried automatically (sample)."
      actions={
        <UnstyledButton
          aria-label={open ? "Collapse delivery" : "Expand delivery"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <LuChevronUp size={14} /> : <LuChevronDown size={14} />}
        </UnstyledButton>
      }
      flush
    >
      <Group px={12} py={10} gap={8} justify="space-between">
        {total === 0 ? (
          <StatusBadge tone="neutral">Not sent</StatusBadge>
        ) : (
          <StatusBadge
            tone={allOk ? "gain" : "caution"}
            icon={allOk ? <LuCircleCheck size={12} /> : <LuCircleX size={12} />}
          >
            Sent to {sent} of {total} channels
          </StatusBadge>
        )}
        {total > 0 ? (
          <SegmentedControl
            size="xs"
            aria-label="Delivery status"
            value={filter}
            onChange={setFilter}
            data={[
              { value: "all", label: "All" },
              { value: "sent", label: "Sent" },
              { value: "failed", label: "Failed" },
            ]}
          />
        ) : null}
      </Group>
      <Collapse in={open}>
        {total === 0 ? (
          <EmptyState
            title="This report was not sent."
            description="No outlook was published, so delivery was skipped."
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title={`No ${filter} deliveries`}
            description="Switch the filter to All to see every channel."
          />
        ) : (
          <Stack gap={0}>
            {rows.map((d) => (
              <Box key={d.id} px={12} py={8} style={{ borderTop: "1px solid var(--kv2-border)" }}>
                <Group justify="space-between" gap={6} wrap="nowrap">
                  <Text size="sm" fw={600}>
                    {d.channel}
                  </Text>
                  <StatusBadge tone={d.result === "sent" ? "gain" : "loss"} size="xs">
                    {d.result === "sent" ? "Sent" : "Failed"}
                  </StatusBadge>
                </Group>
                <Text size="xs" c="dimmed" className="kv2-num">
                  {d.time} IST · {d.audience}
                </Text>
                <Text size="xs" className="kv2-mono" c="dimmed">
                  {d.diagnostics}
                </Text>
              </Box>
            ))}
          </Stack>
        )}
      </Collapse>
    </Panel>
  );
}

export function ReportDetailPage({ day }: { day: string }) {
  const { report, fallback } = useMemo(() => reportFor(day), [day]);
  const { older, newer } = useMemo(() => neighbours(report.day), [report.day]);
  const clipboard = useClipboard({ timeout: 1500 });
  const dayLabel = formatDate(report.day);
  const text = useMemo(() => plainText(report, dayLabel), [report, dayLabel]);
  const outcome = outcomeOf(report);
  const companyById = new Map(companies.map((c) => [c.id, c]));

  const copyText = () => {
    clipboard.copy(text);
    notifications.show({ title: "Copied", message: "Report text copied to the clipboard." });
  };
  const share = () => {
    const url = `${window.location.origin}/v2/reports/${report.day}/`;
    if (navigator.share) {
      void navigator.share({ title: `Daily brief — ${dayLabel}`, url }).catch(() => undefined);
    } else {
      clipboard.copy(url);
      notifications.show({ title: "Link copied", message: url });
    }
  };
  const download = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = `kash-brief-${report.day}.txt`;
    a.click();
    URL.revokeObjectURL(href);
  };

  const navButton = (target: DailyReport | undefined, dir: "older" | "newer") =>
    target ? (
      <Button
        component={AppLink}
        href={`/v2/reports/${target.day}/`}
        variant="subtle"
        size="xs"
        leftSection={dir === "older" ? <LuChevronLeft size={14} /> : undefined}
        rightSection={dir === "newer" ? <LuChevronRight size={14} /> : undefined}
      >
        {dir === "older" ? `Older · ${shortDate(target.day)}` : `${shortDate(target.day)} · Newer`}
      </Button>
    ) : (
      <Button variant="subtle" size="xs" disabled>
        {dir === "older" ? "No older report" : "Latest report"}
      </Button>
    );

  return (
    <Page>
      <PageHeader
        title={`Daily market brief — ${dayLabel}`}
        crumbs={[{ label: "All reports", to: "/v2/reports/" }, { label: dayLabel }]}
        meta={
          <>
            <OutlookBadge outlook={report.outlook} />
            <OutcomeBadge report={report} />
          </>
        }
        description={`Pre-open edition · generated ${report.generatedAt} IST${report.number ? ` · report #${report.number}` : ""} · sample data`}
        actions={
          <>
            <Button variant="default" leftSection={<LuCopy size={14} />} onClick={copyText}>
              {clipboard.copied ? "Copied" : "Copy text"}
            </Button>
            <Button variant="default" leftSection={<LuShare2 size={14} />} onClick={share}>
              Share
            </Button>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button
                  variant="default"
                  leftSection={<LuDownload size={14} />}
                  rightSection={<LuChevronDown size={12} />}
                >
                  Export
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<LuFileText size={14} />} onClick={download}>
                  Download .txt
                </Menu.Item>
                <Menu.Item leftSection={<LuPrinter size={14} />} onClick={() => window.print()}>
                  Print / save as PDF
                </Menu.Item>
                <Menu.Item
                  leftSection={<LuLink size={14} />}
                  onClick={() =>
                    clipboard.copy(`${window.location.origin}/v2/reports/${report.day}/`)
                  }
                >
                  Copy link
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </>
        }
      />

      {fallback ? (
        <Alert color="amber" variant="light" mb={12} title="Report not found">
          There is no report for “{day}”. Showing the latest sample report instead.{" "}
          <Anchor component={AppLink} href="/v2/reports/" inherit>
            Browse all reports
          </Anchor>
        </Alert>
      ) : null}

      <Box
        className="kv2-panel"
        px={8}
        py={4}
        mb={16}
        style={{ position: "sticky", top: 56, zIndex: 5, background: "var(--kv2-surface)" }}
      >
        <Group justify="space-between" gap={6} wrap="nowrap">
          {navButton(older, "older")}
          <Group gap={6} wrap="nowrap" visibleFrom="xs">
            <Text size="sm" fw={600} className="kv2-num">
              {dayLabel}
            </Text>
            <OutlookBadge outlook={report.outlook} size="xs" />
          </Group>
          {navButton(newer, "newer")}
        </Group>
      </Box>

      <Grid gutter={16}>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap={16} maw={760}>
            <div id="outlook">
              <Panel
                title="1. Outlook"
                info="The model's call for today's Sample Index 50 direction. Strength combines the news score and global cues on a 0–10 scale; 7+ is strong."
              >
                <Stack gap={12}>
                  <Group gap={12} wrap="wrap">
                    <OutlookBadge outlook={report.outlook} />
                    {report.outlook !== "na" ? <StrengthMeter score={report.strength} /> : null}
                  </Group>
                  <Text size="sm">{report.summary}</Text>
                  <KpiGrid cols={3}>
                    <KpiTile
                      label="Signal strength"
                      value={
                        <span className="kv2-num">
                          {report.outlook === "na" ? "—" : `${report.strength.toFixed(1)} / 10`}
                        </span>
                      }
                      info="Overall conviction of the outlook. Below 5 is weak, 5–7 moderate, 7+ strong."
                    />
                    <KpiTile
                      label="News sentiment"
                      value={<span className="kv2-num">{report.newsScore.toFixed(1)} / 10</span>}
                      info="Average score of the articles scored before the 07:30 IST cut-off, rescaled to 0–10."
                    />
                    <KpiTile
                      label="Global cues"
                      value={<span className="kv2-num">{report.globalScore.toFixed(1)} / 10</span>}
                      info="How supportive overnight markets, crude, yields and currency are for a positive open."
                    />
                  </KpiGrid>
                  <Group gap={8}>
                    <Text size="xs" c="dimmed">
                      Actual result:
                    </Text>
                    {report.actualPct == null ? (
                      <Text size="xs" c="dimmed">
                        {report.outlook === "na"
                          ? "Not scored"
                          : "Session still open — result after 15:30 IST"}
                      </Text>
                    ) : (
                      <>
                        <Delta value={report.actualPct} size="xs" />
                        <Text size="xs" c="dimmed">
                          Sample Index 50 close
                        </Text>
                        {outcome === "hit" || outcome === "miss" ? (
                          <OutcomeBadge report={report} />
                        ) : null}
                      </>
                    )}
                  </Group>
                </Stack>
              </Panel>
            </div>

            <div id="index-closes">
              <Panel
                title="2. Index closes"
                info="Previous session closes used as the base for today's outlook."
                flush
              >
                <div className="kv2-table-wrap">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Index</Table.Th>
                        <Table.Th data-align="right">Close</Table.Th>
                        <Table.Th data-align="right">Change</Table.Th>
                        <Table.Th data-align="right">Change %</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {report.indexCloses.map((i) => (
                        <Table.Tr key={i.symbol}>
                          <Table.Td>
                            <Text size="sm" fw={500}>
                              {i.name}
                            </Text>
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(i.close, 2)}
                          </Table.Td>
                          <Table.Td data-align="right">
                            <Delta value={i.change} kind="points" size="xs" />
                          </Table.Td>
                          <Table.Td data-align="right">
                            <Delta value={i.changePct} size="xs" />
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </div>
              </Panel>
            </div>

            <div id="key-news">
              <Panel
                title="3. Key news"
                info="The highest-impact scored articles behind today's outlook. Score runs from −1 (very negative) to +1 (very positive)."
                actions={
                  <Anchor component={AppLink} href="/v2/news/" size="xs">
                    All news
                  </Anchor>
                }
                flush
              >
                <Stack gap={0}>
                  {report.news.map((n, i) => (
                    <Box
                      key={n.id}
                      px={12}
                      py={10}
                      style={i ? { borderTop: "1px solid var(--kv2-border)" } : undefined}
                    >
                      <Group justify="space-between" align="flex-start" gap={8} wrap="nowrap">
                        <Text size="sm" fw={600}>
                          {n.title}
                        </Text>
                        <SentimentPill score={n.score} size="xs" />
                      </Group>
                      <Text size="xs" c="dimmed" mt={2}>
                        {n.summary}
                      </Text>
                      <Group gap={6} mt={6}>
                        <Text size="xs" c="dimmed">
                          {n.source} ·
                        </Text>
                        {n.companyIds.map((id) => {
                          const c = companyById.get(id);
                          return c ? (
                            <Anchor
                              key={id}
                              component={AppLink}
                              href={`/v2/companies/${id}/`}
                              underline="never"
                            >
                              <SymbolChip symbol={c.symbol} />
                            </Anchor>
                          ) : null;
                        })}
                      </Group>
                    </Box>
                  ))}
                </Stack>
              </Panel>
            </div>

            <div id="ipo-watch">
              <Panel
                title="4. IPO watch"
                actions={
                  <Anchor component={AppLink} href="/v2/ipos/" size="xs">
                    All IPOs
                  </Anchor>
                }
                flush
              >
                <Stack gap={0}>
                  {report.ipos.map((ipo, i) => (
                    <Group
                      key={ipo.name}
                      px={12}
                      py={8}
                      justify="space-between"
                      gap={8}
                      style={i ? { borderTop: "1px solid var(--kv2-border)" } : undefined}
                    >
                      <div>
                        <Text size="sm" fw={600}>
                          {ipo.name}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {ipo.detail}
                        </Text>
                      </div>
                      <StatusBadge tone={ipo.tone} size="xs">
                        {ipo.status}
                      </StatusBadge>
                    </Group>
                  ))}
                </Stack>
              </Panel>
            </div>

            <div id="global-cues">
              <Panel
                title="5. Global cues"
                info="Overnight and early-morning markets that tend to move the domestic open. Snapshot at 07:30 IST."
              >
                <SimpleGrid cols={{ base: 1, xs: 2, sm: 3 }} spacing={8}>
                  {report.globalCues.map((g) => (
                    <Box
                      key={g.label}
                      p={8}
                      style={{ border: "1px solid var(--kv2-border)", borderRadius: 4 }}
                    >
                      <Text className="kv2-eyebrow">{g.label}</Text>
                      <Group gap={6} justify="space-between" wrap="nowrap">
                        <Text size="sm" fw={600} className="kv2-num">
                          {g.value}
                        </Text>
                        <Delta value={g.changePct} size="xs" />
                      </Group>
                      <Text size="xs" c="dimmed">
                        {g.note}
                      </Text>
                    </Box>
                  ))}
                </SimpleGrid>
              </Panel>
            </div>

            <div id="delivered-text">
              <Panel
                title="Delivered text"
                info="The exact plain-text message sent to Telegram and email subscribers."
                actions={
                  <Button
                    size="xs"
                    variant="subtle"
                    leftSection={<LuCopy size={12} />}
                    onClick={copyText}
                  >
                    {clipboard.copied ? "Copied" : "Copy"}
                  </Button>
                }
              >
                <div className="kv2-terminal">
                  <pre
                    style={{ margin: 0, padding: 12, whiteSpace: "pre-wrap", overflowX: "auto" }}
                  >
                    {text}
                  </pre>
                </div>
              </Panel>
            </div>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap={16}>
            <DeliveryPanel report={report} />
            <Panel title="On this page">
              <Stack gap={2}>
                {sections.map((s) => (
                  <Anchor key={s.id} href={`#${s.id}`} size="sm" c="var(--kv2-text-muted)">
                    {s.label}
                  </Anchor>
                ))}
              </Stack>
            </Panel>
            <Panel
              title="Diagnostics"
              info="Build details for this report. Useful when a report looks wrong or late."
            >
              <DescriptionList
                items={[
                  ["Generated", `${report.generatedAt} IST`],
                  [
                    "Articles scored",
                    <span className="kv2-num">{40 + Math.round(report.newsScore * 5)}</span>,
                  ],
                  ["Build time", <span className="kv2-num">0.4 s</span>],
                  ["Model", "Sample model v1"],
                ]}
              />
              {sampleUser.staff ? (
                <Stack gap={4} mt={12}>
                  <Button
                    variant="default"
                    size="xs"
                    leftSection={<LuRefreshCw size={12} />}
                    onClick={() =>
                      notifications.show({
                        title: "Rebuild queued (sample)",
                        message: `Report for ${dayLabel} will be rebuilt.`,
                      })
                    }
                  >
                    Rebuild report
                  </Button>
                  <Group gap={4}>
                    <Text size="xs" c="dimmed">
                      Staff only · does not re-send messages
                    </Text>
                    <InfoTip>
                      Rebuilding regenerates the text from stored inputs. Delivery is not repeated.
                    </InfoTip>
                  </Group>
                </Stack>
              ) : null}
            </Panel>
          </Stack>
        </Grid.Col>
      </Grid>
    </Page>
  );
}
