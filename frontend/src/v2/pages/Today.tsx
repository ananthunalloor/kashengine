import {
  Anchor,
  Button,
  Collapse,
  Divider,
  Grid,
  Group,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import {
  LuArrowRight,
  LuChevronDown,
  LuChevronRight,
  LuDownload,
  LuExternalLink,
  LuMail,
  LuRefreshCw,
  LuSend,
  LuTriangleAlert,
  LuWebhook,
} from "react-icons/lu";

import {
  AppLink,
  Delta,
  DirectionBadge,
  EmptyState,
  FreshnessTag,
  InfoTip,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  ScoreBar,
  SentimentPill,
  Sparkline,
  StatusBadge,
  StrengthMeter,
  SymbolChip,
  formatDate,
  formatInr,
  formatNumber,
  formatPercent,
} from "../components";
import type { Tone } from "../components";
import { indices } from "../mock/data";
import {
  breadth,
  deliveryStatus,
  indexExtras,
  ipoGroups,
  latestReport,
  newsHighlights,
  outlook,
  stocksToWatch,
  todayMeta,
  topMovers,
} from "../mock/today";
import type { IpoCard, NewsBias, WatchStock } from "../mock/today";

const biasMeta: Record<NewsBias, { tone: Tone; label: string }> = {
  bullish: { tone: "gain", label: "▲ Bullish" },
  bearish: { tone: "loss", label: "▼ Bearish" },
  mixed: { tone: "caution", label: "– Mixed" },
  none: { tone: "neutral", label: "No clear edge" },
};

export function TodayPage() {
  const [refreshing, setRefreshing] = useState(false);
  const [asOf, setAsOf] = useState(todayMeta.asOf);

  const refresh = () => {
    setRefreshing(true);
    window.setTimeout(() => {
      setRefreshing(false);
      setAsOf("11:43");
      notifications.show({
        title: "Dashboard refreshed",
        message: "Sample data reloaded at 11:43 IST.",
      });
    }, 700);
  };

  const exportBrief = () =>
    notifications.show({
      title: "Brief exported",
      message: `Sample brief for ${formatDate(todayMeta.date)} prepared as PDF (mock).`,
      color: "emerald",
    });

  return (
    <Page>
      <PageHeader
        title="Today"
        meta={<FreshnessTag state="live" detail={`as of ${asOf} IST`} />}
        description={`${formatDate(todayMeta.date)} · Your latest saved outlook, stories, and issues.`}
        actions={
          <>
            <Button
              variant="default"
              leftSection={<LuRefreshCw size={14} />}
              loading={refreshing}
              onClick={refresh}
            >
              Refresh
            </Button>
            <Button leftSection={<LuDownload size={14} />} onClick={exportBrief}>
              Export brief
            </Button>
          </>
        }
      />

      <Stack gap={16}>
        <Grid gutter={16}>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <OutlookCard />
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Stack gap={12}>
              <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing={12}>
                {indices.map((index) => {
                  const extra = indexExtras[index.symbol];
                  return (
                    <KpiTile
                      key={index.symbol}
                      label={index.name}
                      value={<span className="kv2-num">{formatNumber(index.last, 2)}</span>}
                      delta={<Delta value={index.changePct} size="xs" />}
                      hint={
                        extra
                          ? `${formatNumber(extra.low, 0)} – ${formatNumber(extra.high, 0)}`
                          : undefined
                      }
                      info={
                        extra
                          ? `Previous close ${formatNumber(extra.prevClose, 2)}. Day range shown below the change. Last trade ${extra.lastTrade} IST.`
                          : undefined
                      }
                      aside={<Sparkline data={index.trend} w={56} h={20} />}
                    />
                  );
                })}
              </SimpleGrid>
              <BreadthPanel />
            </Stack>
          </Grid.Col>
        </Grid>

        <Grid gutter={16}>
          <Grid.Col span={{ base: 12, lg: 7 }}>
            <StocksToWatch />
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 5 }}>
            <NewsPanel />
          </Grid.Col>
        </Grid>

        <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }} spacing={16}>
          <IposPanel />
          <MoversPanel />
          <Stack gap={16}>
            <ReportPanel />
            <DeliveryPanel />
          </Stack>
        </SimpleGrid>
      </Stack>
    </Page>
  );
}

function OutlookCard() {
  const [showCues, setShowCues] = useState(false);
  const { stats } = outlook;
  return (
    <Panel
      title={`Outlook for ${formatDate(todayMeta.date)}`}
      info="Saved before the open. Combines scored news since the previous close with overnight global market moves. It is a sample signal, not advice."
      actions={<DirectionBadge direction={outlook.direction} />}
      footer={
        <Anchor component={AppLink} href="/v2/markets/" size="xs">
          See the history <LuArrowRight size={11} />
        </Anchor>
      }
    >
      <Stack gap={12}>
        <div>
          <span className="kv2-eyebrow">{outlook.index}</span>
          <Text fz={20} fw={600} lh="28px">
            Likely to <span className="kv2-gain">rise ▲</span>
          </Text>
          <Text size="xs" c="dimmed">
            {outlook.notes}
          </Text>
        </div>
        <Stack gap={4}>
          <Group gap={4}>
            <span className="kv2-eyebrow">Signal strength</span>
            <InfoTip>
              How strongly the inputs agree, from 0 (no edge) to 10 (all inputs point the same way).
            </InfoTip>
          </Group>
          <StrengthMeter score={outlook.strength} tone="gain" />
        </Stack>
        <SimpleGrid cols={3} spacing={8}>
          <MiniStat
            label="News score"
            value={outlook.newsScore.toFixed(1)}
            hint={`${outlook.newsArticles} articles`}
            info="Average score of today's market-wide news, scaled to 0–10. Above 5 leans positive."
          />
          <MiniStat
            label="Global cues"
            value={outlook.globalScore.toFixed(1)}
            hint="overnight"
            info="Overnight moves in overseas indices, currencies and commodities, scaled to 0–10."
          />
          <MiniStat
            label="Accuracy"
            value={formatPercent(stats.accuracy, { signed: false, decimals: 1 })}
            hint={`${stats.correct}/${stats.total} days`}
            info={`Share of the last ${stats.total} trading days where the predicted direction matched the close. Baseline (always predicting the most common direction) is ${stats.baseline}%.`}
          />
        </SimpleGrid>
        <Stack gap={4}>
          <Group justify="space-between">
            <Text size="xs" c="dimmed">
              Track record vs baseline
            </Text>
            <Text size="xs" className="kv2-num">
              {stats.accuracy}% vs {stats.baseline}%
            </Text>
          </Group>
          <Progress.Root size={6}>
            <Progress.Section value={stats.accuracy} color="indigo.6" />
          </Progress.Root>
        </Stack>
        <Divider />
        <UnstyledButton onClick={() => setShowCues((v) => !v)} aria-expanded={showCues}>
          <Group gap={4}>
            {showCues ? <LuChevronDown size={14} /> : <LuChevronRight size={14} />}
            <Text size="xs" fw={600}>
              Strongest cues (top {outlook.cues.length})
            </Text>
          </Group>
        </UnstyledButton>
        <Collapse in={showCues}>
          <div className="kv2-table-wrap">
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Instrument</Table.Th>
                  <Table.Th data-align="right">Change</Table.Th>
                  <Table.Th data-align="right">Date</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {outlook.cues.map((cue) => (
                  <Table.Tr key={cue.instrument}>
                    <Table.Td>{cue.instrument}</Table.Td>
                    <Table.Td data-align="right">
                      <Delta value={cue.change} size="xs" />
                    </Table.Td>
                    <Table.Td data-align="right">
                      <Text size="xs" c="dimmed">
                        {formatDate(cue.date)}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </div>
        </Collapse>
      </Stack>
    </Panel>
  );
}

function MiniStat({
  label,
  value,
  hint,
  info,
}: {
  label: string;
  value: string;
  hint: string;
  info: string;
}) {
  return (
    <Stack gap={0}>
      <Group gap={2} wrap="nowrap">
        <span className="kv2-eyebrow">{label}</span>
        <InfoTip>{info}</InfoTip>
      </Group>
      <Text fw={600} className="kv2-num">
        {value}
      </Text>
      <Text size="xs" c="dimmed">
        {hint}
      </Text>
    </Stack>
  );
}

function BreadthPanel() {
  const total = breadth.advancers + breadth.decliners + breadth.unchanged;
  const pct = (n: number) => (n / total) * 100;
  return (
    <Panel
      title="Market breadth"
      info="How many tracked stocks are up (advancers) versus down (decliners) since the previous close."
      actions={
        <Text size="xs" c="dimmed" className="kv2-num">
          {formatNumber(total)} tracked
        </Text>
      }
    >
      <Stack gap={6}>
        <Progress.Root size={10}>
          <Progress.Section value={pct(breadth.advancers)} color="emerald.6" />
          <Progress.Section value={pct(breadth.unchanged)} color="slate.4" />
          <Progress.Section value={pct(breadth.decliners)} color="red.6" />
        </Progress.Root>
        <Group justify="space-between" gap={8}>
          <Text size="xs" className="kv2-num kv2-gain">
            ▲ {formatNumber(breadth.advancers)} adv ({pct(breadth.advancers).toFixed(0)}%)
          </Text>
          <Text size="xs" c="dimmed" className="kv2-num">
            – {breadth.unchanged} unch
          </Text>
          <Text size="xs" className="kv2-num kv2-loss">
            ▼ {formatNumber(breadth.decliners)} dec ({pct(breadth.decliners).toFixed(0)}%)
          </Text>
        </Group>
      </Stack>
    </Panel>
  );
}

function StocksToWatch() {
  const [open, setOpen] = useState<string | null>(stocksToWatch[0]?.companyId ?? null);
  return (
    <Panel
      title="Stocks to watch today"
      info="Companies with the most news since the previous close. News bias summarises whether stories are good or bad for the stock; news balance runs from −1 (all negative) to +1 (all positive) and is not a probability."
      actions={
        <StatusBadge tone="gain" dot size="xs">
          Session open at snapshot
        </StatusBadge>
      }
      footer={
        <Text size="xs" c="dimmed">
          Snapshot 11:40 IST · news window since previous close (15:30 IST, 09 Jan 2026)
        </Text>
      }
      flush
    >
      {stocksToWatch.length === 0 ? (
        <EmptyState
          title="No news-backed stocks to watch yet"
          description="Check back after the morning news run."
        />
      ) : (
        stocksToWatch.map((stock, i) => (
          <div key={stock.companyId}>
            {i > 0 ? <Divider /> : null}
            <WatchRow
              stock={stock}
              open={open === stock.companyId}
              onToggle={() => setOpen((cur) => (cur === stock.companyId ? null : stock.companyId))}
            />
          </div>
        ))
      )}
    </Panel>
  );
}

function WatchRow({
  stock,
  open,
  onToggle,
}: {
  stock: WatchStock;
  open: boolean;
  onToggle: () => void;
}) {
  const bias = biasMeta[stock.bias];
  return (
    <div style={{ padding: "10px 12px" }}>
      <Group justify="space-between" align="flex-start" gap={8} wrap="wrap">
        <Group gap={8} wrap="nowrap" align="flex-start" style={{ minWidth: 0, flex: "1 1 220px" }}>
          <UnstyledButton
            onClick={onToggle}
            aria-expanded={open}
            aria-label="Show headlines"
            c="dimmed"
            mt={2}
          >
            {open ? <LuChevronDown size={14} /> : <LuChevronRight size={14} />}
          </UnstyledButton>
          <Stack gap={2} style={{ minWidth: 0 }}>
            <Group gap={6} wrap="wrap">
              <Anchor
                component={AppLink}
                href={`/v2/companies/${stock.companyId}/`}
                fw={600}
                size="sm"
              >
                {stock.name}
              </Anchor>
              <SymbolChip symbol={stock.symbol} />
            </Group>
            <Text size="xs" c="dimmed">
              {stock.sector} · {stock.articles} articles · {stock.sources} sources · {stock.latest}
            </Text>
          </Stack>
        </Group>
        <Group gap={12} wrap="wrap" justify="flex-end">
          <Stack gap={0} align="flex-end">
            <Text size="sm" fw={600} className="kv2-num">
              {formatInr(stock.price)}
            </Text>
            <Delta value={stock.changePct} size="xs" />
          </Stack>
          <Stack gap={4} align="flex-end">
            <StatusBadge tone={bias.tone} size="xs">
              {bias.label}
            </StatusBadge>
            <Group gap={4} wrap="nowrap">
              <ScoreBar score={stock.balance} width={64} />
              <Text size="xs" className="kv2-num" c="dimmed">
                {stock.balance > 0 ? "+" : ""}
                {stock.balance.toFixed(2)}
              </Text>
            </Group>
          </Stack>
        </Group>
      </Group>
      {stock.articles === 1 ? (
        <Group gap={4} mt={6} ml={22}>
          <StatusBadge tone="caution" size="xs" icon={<LuTriangleAlert size={11} />}>
            Single-article evidence
          </StatusBadge>
        </Group>
      ) : null}
      <Collapse in={open}>
        <Stack gap={8} mt={8} ml={22}>
          <Text size="xs" c="dimmed">
            <span className="kv2-gain">▲ {stock.positive} positive</span> ·{" "}
            <span className="kv2-loss">▼ {stock.negative} negative</span> stories
          </Text>
          {stock.headlines.slice(0, 3).map((h) => (
            <div key={h.title}>
              <Anchor href="https://example.com/" target="_blank" rel="noreferrer" size="sm">
                {h.title} <LuExternalLink size={11} />
              </Anchor>
              <Text size="xs" c="dimmed">
                {h.source} · {h.time} · {h.reason}
              </Text>
            </div>
          ))}
        </Stack>
      </Collapse>
    </div>
  );
}

function NewsPanel() {
  const [filter, setFilter] = useState("all");
  const items = newsHighlights.filter((n) =>
    filter === "all" ? true : filter === "positive" ? n.score > 0 : n.score < 0,
  );
  return (
    <Panel
      title="Today's scored news"
      info="Each story is scored from −1 (bad for stocks) to +1 (good for stocks). The reason line explains the score."
      actions={
        <SegmentedControl
          size="xs"
          value={filter}
          onChange={setFilter}
          data={[
            { value: "all", label: "All" },
            { value: "positive", label: "Good" },
            { value: "negative", label: "Bad" },
          ]}
        />
      }
      footer={
        <Anchor component={AppLink} href="/v2/news/" size="xs">
          All news <LuArrowRight size={11} />
        </Anchor>
      }
    >
      {items.length === 0 ? (
        <EmptyState title="No stories match" description="Try another filter." />
      ) : (
        <Stack gap={10}>
          {items.map((n, i) => (
            <div key={n.id}>
              {i > 0 ? <Divider mb={10} /> : null}
              <Group gap={6} mb={2} wrap="wrap">
                <SentimentPill score={n.score} size="xs" />
                <SymbolChip symbol={n.symbol} />
                <Text size="xs" c="dimmed">
                  {n.source} · {n.time}
                </Text>
              </Group>
              <Anchor
                href="https://example.com/"
                target="_blank"
                rel="noreferrer"
                size="sm"
                c="var(--kv2-text)"
              >
                {n.title} <LuExternalLink size={11} />
              </Anchor>
              <Text size="xs" c="dimmed">
                Why: {n.reason}
              </Text>
            </div>
          ))}
        </Stack>
      )}
    </Panel>
  );
}

const verdictTone: Record<IpoCard["verdict"], Tone> = {
  "Likely positive": "gain",
  Neutral: "neutral",
  Avoid: "loss",
};

function IposPanel() {
  const tabs = [
    { value: "likely", label: "Likely to do well" },
    { value: "open", label: "Open now" },
    { value: "soon", label: "Opening soon" },
  ] as const;
  return (
    <Panel
      title="IPOs"
      info="Verdict and score (0–10) combine subscription, issue size, valuation and sample grey-market premium (an unofficial, indicative price)."
      footer={
        <Anchor component={AppLink} href="/v2/ipos/" size="xs">
          All IPOs <LuArrowRight size={11} />
        </Anchor>
      }
    >
      <Tabs defaultValue="likely">
        <Tabs.List mb={8}>
          {tabs.map((t) => (
            <Tabs.Tab key={t.value} value={t.value} fz="xs">
              {t.label} ({ipoGroups[t.value].length})
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {tabs.map((t) => (
          <Tabs.Panel key={t.value} value={t.value}>
            <Stack gap={8}>
              {ipoGroups[t.value].map((ipo) => (
                <div key={ipo.id} className="kv2-kpi">
                  <Group justify="space-between" wrap="nowrap" gap={8}>
                    <Anchor
                      component={AppLink}
                      href={`/v2/ipos/${ipo.id}/`}
                      fw={600}
                      size="sm"
                      truncate
                    >
                      {ipo.name}
                    </Anchor>
                    <StatusBadge tone={verdictTone[ipo.verdict]} size="xs">
                      {ipo.verdict}
                    </StatusBadge>
                  </Group>
                  <Text size="xs" c="dimmed" className="kv2-num">
                    Band {formatInr(ipo.band[0], { decimals: 0 })} –{" "}
                    {formatInr(ipo.band[1], { decimals: 0 })} · {ipo.dates}
                  </Text>
                  <Group justify="space-between" gap={8}>
                    <StrengthMeter score={ipo.score} showValue={false} />
                    <Group gap={4}>
                      <Text size="xs" c="dimmed">
                        GMP
                      </Text>
                      <Delta value={ipo.premiumPct} size="xs" decimals={1} />
                    </Group>
                  </Group>
                </div>
              ))}
            </Stack>
          </Tabs.Panel>
        ))}
      </Tabs>
    </Panel>
  );
}

function MoversPanel() {
  const [side, setSide] = useState<"gainers" | "losers">("gainers");
  return (
    <Panel
      title="Top movers"
      info="Biggest percentage moves among tracked companies since the previous close."
      actions={
        <SegmentedControl
          size="xs"
          value={side}
          onChange={(v) => setSide(v as "gainers" | "losers")}
          data={[
            { value: "gainers", label: "Gainers" },
            { value: "losers", label: "Losers" },
          ]}
        />
      }
      footer={
        <Anchor component={AppLink} href="/v2/markets/" size="xs">
          Markets <LuArrowRight size={11} />
        </Anchor>
      }
    >
      <Stack gap={8}>
        {topMovers[side].map((c) => (
          <Group key={c.id} justify="space-between" wrap="nowrap" gap={8}>
            <Stack gap={0} style={{ minWidth: 0 }}>
              <Anchor
                component={AppLink}
                href={`/v2/companies/${c.id}/`}
                size="sm"
                fw={600}
                truncate
              >
                {c.name}
              </Anchor>
              <Text size="xs" c="dimmed" className="kv2-mono">
                {c.symbol} · {formatInr(c.last)}
              </Text>
            </Stack>
            <Group gap={8} wrap="nowrap">
              <Sparkline data={c.trend} w={56} h={20} />
              <Delta value={c.changePct} size="xs" />
            </Group>
          </Group>
        ))}
      </Stack>
    </Panel>
  );
}

function ReportPanel() {
  return (
    <Panel
      title="Latest daily brief"
      actions={
        <Text size="xs" c="dimmed">
          {formatDate(latestReport.date)}
        </Text>
      }
    >
      <Stack gap={6}>
        <Text size="sm" fw={600}>
          {latestReport.title}
        </Text>
        <Text size="xs" c="dimmed" lineClamp={3}>
          {latestReport.lines.join(" ")}
        </Text>
        <Group justify="space-between">
          <Text size="xs" c="dimmed">
            {latestReport.readMinutes} min read
          </Text>
          <Button
            component={AppLink}
            href={`/v2/reports/${latestReport.date}/`}
            variant="subtle"
            size="xs"
            rightSection={<LuArrowRight size={12} />}
          >
            Read
          </Button>
        </Group>
      </Stack>
    </Panel>
  );
}

const channelIcon = { Email: LuMail, Telegram: LuSend, Webhook: LuWebhook } as const;

function DeliveryPanel() {
  return (
    <Panel
      title="Today's delivery"
      info="Where this morning's brief was sent and whether each channel accepted it."
      footer={
        <Anchor component={AppLink} href="/v2/delivery/" size="xs">
          Manage delivery <LuArrowRight size={11} />
        </Anchor>
      }
    >
      <Stack gap={8}>
        {deliveryStatus.map((d) => {
          const Icon = channelIcon[d.channel as keyof typeof channelIcon];
          return (
            <Group key={d.channel} justify="space-between" wrap="nowrap" gap={8}>
              <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
                <Icon size={14} />
                <Stack gap={0} style={{ minWidth: 0 }}>
                  <Text size="sm">{d.channel}</Text>
                  <Text size="xs" c="dimmed" truncate>
                    {d.target}
                  </Text>
                </Stack>
              </Group>
              <Group gap={6} wrap="nowrap">
                <Text size="xs" c="dimmed">
                  {d.time}
                </Text>
                <StatusBadge tone={d.state === "sent" ? "gain" : "loss"} size="xs" dot>
                  {d.state === "sent" ? "Sent" : "Failed"}
                </StatusBadge>
              </Group>
            </Group>
          );
        })}
      </Stack>
    </Panel>
  );
}
