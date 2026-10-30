import { BarChart, DonutChart, LineChart } from "@mantine/charts";
import {
  Accordion,
  Alert,
  Anchor,
  Button,
  Grid,
  Group,
  Progress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { LuBookmarkPlus, LuExternalLink, LuInfo } from "react-icons/lu";

import {
  AppLink,
  DataTable,
  Delta,
  DescriptionList,
  DirectionBadge,
  EmptyState,
  FreshnessTag,
  InfoTip,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  PriceChartPanel,
  ScoreBar,
  SentimentPill,
  StatusBadge,
  StrengthMeter,
  SymbolChip,
  formatCompactInr,
  formatDate,
  formatInr,
  formatNumber,
  formatPercent,
  formatSigned,
} from "../components";
import type { Column, Tone } from "../components";
import { companyDetail, companySeed, findCompany } from "../mock/companies";
import type { CompanyNews, DeliveryDay, MarketDepthLevel } from "../mock/companies";
import { mockCandles } from "../mock/generate";
import type { Candle } from "../mock/generate";

const crore = 1e7;

function Muted({ children }: { children: ReactNode }) {
  return (
    <Group gap={6} wrap="nowrap" align="flex-start">
      <LuInfo size={14} style={{ flexShrink: 0, marginTop: 2, color: "var(--kv2-text-muted)" }} />
      <Text size="xs" c="dimmed">
        {children}
      </Text>
    </Group>
  );
}

/** Stacked +/0/− bar for news sentiment counts. */
function SentimentBar({
  positive,
  neutral,
  negative,
}: {
  positive: number;
  neutral: number;
  negative: number;
}) {
  const total = positive + neutral + negative || 1;
  return (
    <Progress.Root size={6} aria-label="News sentiment split">
      <Progress.Section value={(positive / total) * 100} color="var(--kv2-gain)" />
      <Progress.Section value={(neutral / total) * 100} color="var(--kv2-neutral)" />
      <Progress.Section value={(negative / total) * 100} color="var(--kv2-loss)" />
    </Progress.Root>
  );
}

const valuationTone: Record<string, Tone> = {
  "In line": "info",
  "Sector premium": "caution",
  "Sector discount": "gain",
  "Mixed valuation": "neutral",
  "Insufficient data": "neutral",
};

const newsColumns: Column<CompanyNews>[] = [
  {
    key: "title",
    header: "Headline",
    sortValue: (n) => n.title,
    render: (n) => (
      <Stack gap={2} style={{ minWidth: 220 }}>
        <Text size="sm" fw={500}>
          {n.title}
        </Text>
        <Text size="xs" c="dimmed">
          {n.source} · {formatDate(n.date)}, {n.time} IST
        </Text>
      </Stack>
    ),
  },
  {
    key: "sentiment",
    header: "Sentiment",
    sortValue: (n) => n.score,
    render: (n) => (
      <Stack gap={4}>
        <SentimentPill score={n.score} size="xs" />
        <ScoreBar score={n.score} width={80} />
      </Stack>
    ),
  },
  {
    key: "relevance",
    header: "Relevance",
    align: "right",
    sortValue: (n) => n.relevance,
    render: (n) => <span className="kv2-num">{formatNumber(n.relevance * 100)}%</span>,
    hideOnMobile: true,
  },
  {
    key: "reason",
    header: "Why it scored this way",
    render: (n) => (
      <Text size="xs" c="dimmed">
        {n.reason}
      </Text>
    ),
    hideOnMobile: true,
  },
];

const deliveryColumns: Column<DeliveryDay>[] = [
  { key: "date", header: "Date", sortValue: (d) => d.date, render: (d) => formatDate(d.date) },
  {
    key: "close",
    header: "Close",
    align: "right",
    sortValue: (d) => d.close,
    render: (d) => <span className="kv2-num">{formatInr(d.close)}</span>,
  },
  {
    key: "volume",
    header: "Traded qty",
    align: "right",
    sortValue: (d) => d.volume,
    render: (d) => <span className="kv2-num">{formatNumber(d.volume)}</span>,
    hideOnMobile: true,
  },
  {
    key: "delivered",
    header: "Delivered qty",
    align: "right",
    sortValue: (d) => d.delivered,
    render: (d) => <span className="kv2-num">{formatNumber(d.delivered)}</span>,
    hideOnMobile: true,
  },
  {
    key: "pct",
    header: "Delivery %",
    align: "right",
    sortValue: (d) => d.deliveryPct,
    render: (d) => (
      <Group gap={8} justify="flex-end" wrap="nowrap">
        <Progress
          value={d.deliveryPct}
          size={4}
          w={60}
          color={d.deliveryPct >= 60 ? "emerald" : "slate"}
        />
        <span className="kv2-num">{formatNumber(d.deliveryPct, 1)}%</span>
      </Group>
    ),
  },
];

type ForecastResult = {
  origin: string;
  target: string;
  originClose: number;
  predicted: number;
  actual: number;
  error: number;
  directionMatched: boolean;
};

function forecastResults(candles: Candle[], horizon: number): ForecastResult[] {
  const results: ForecastResult[] = [];
  for (let originIndex = 20; originIndex + horizon - 1 < candles.length; originIndex += horizon) {
    const history = candles.slice(originIndex - 20, originIndex);
    const mean = history.reduce((sum, candle) => sum + candle.close, 0) / history.length;
    const meanX = (history.length - 1) / 2;
    const denominator = history.reduce((sum, _, i) => sum + (i - meanX) ** 2, 0);
    const slope =
      denominator === 0
        ? 0
        : history.reduce((sum, candle, i) => sum + (i - meanX) * (candle.close - mean), 0) /
          denominator;
    const origin = candles[originIndex - 1];
    const target = candles[originIndex + horizon - 1];
    const predicted = mean + slope * (history.length + horizon - 1 - meanX);
    const predictedMove = predicted - origin.close;
    const actualMove = target.close - origin.close;
    results.push({
      origin: origin.date,
      target: target.date,
      originClose: origin.close,
      predicted,
      actual: target.close,
      error: predicted - target.close,
      directionMatched: Math.sign(predictedMove) === Math.sign(actualMove),
    });
  }
  return results;
}

function marketDepthRows(levels: MarketDepthLevel[]) {
  return levels.map((level, index) => ({ ...level, level: index + 1 }));
}

export function MockCompanyDetailPage({ id }: { id: string }) {
  const company = findCompany(id);
  const detail = useMemo(() => companyDetail(company), [company]);
  const candles = useMemo(() => mockCandles(260, company.last, companySeed(company)), [company]);
  const [tab, setTab] = useState<string | null>("overview");
  const [period, setPeriod] = useState("quarterly");
  const [newsSentiment, setNewsSentiment] = useState<string | null>(null);
  const [newsSource, setNewsSource] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(5);

  const change = company.last - detail.prevClose;
  const s = detail.sentiment;
  const valuationRows = detail.multiples.map((multiple) => {
    const comparable =
      Number.isFinite(multiple.company) &&
      Number.isFinite(multiple.sector) &&
      multiple.company > 0 &&
      multiple.sector > 0;
    return {
      ...multiple,
      comparable,
      difference: comparable ? (multiple.company / multiple.sector - 1) * 100 : null,
    };
  });
  const comparableCount = valuationRows.filter((row) => row.comparable).length;
  const hasPremium = valuationRows.some((row) => row.difference !== null && row.difference > 10);
  const hasDiscount = valuationRows.some((row) => row.difference !== null && row.difference < -10);
  const valuationState =
    comparableCount === 0
      ? "Insufficient data"
      : hasPremium && hasDiscount
        ? "Mixed valuation"
        : hasPremium
          ? "Sector premium"
          : hasDiscount
            ? "Sector discount"
            : "In line";
  const totalDepthQty = detail.totalBuyQty + detail.totalSellQty;
  const buyPressurePct = totalDepthQty > 0 ? (detail.totalBuyQty / totalDepthQty) * 100 : 0;

  const news = detail.news.filter(
    (n) =>
      (!newsSource || n.source === newsSource) &&
      (!newsSentiment ||
        (newsSentiment === "positive" && n.score >= 0.15) ||
        (newsSentiment === "negative" && n.score <= -0.15) ||
        (newsSentiment === "neutral" && Math.abs(n.score) < 0.15)),
  );

  const avgDelivery =
    detail.delivery.reduce((sum, d) => sum + d.deliveryPct, 0) / detail.delivery.length;
  const latestDelivery = detail.delivery[detail.delivery.length - 1];
  const deliveryChart = detail.delivery.map((d) => ({
    date: formatDate(d.date).slice(0, 6),
    Delivered: Math.round(d.delivered / 1000),
    Intraday: Math.round((d.volume - d.delivered) / 1000),
    "Delivery %": d.deliveryPct,
  }));
  const predictions = useMemo(() => forecastResults(candles, horizon), [candles, horizon]);
  const predictionSummary = useMemo(() => {
    if (!predictions.length) return null;
    const absoluteError = predictions.reduce((sum, row) => sum + Math.abs(row.error), 0);
    const baselineError = predictions.reduce(
      (sum, row) => sum + Math.abs(row.originClose - row.actual),
      0,
    );
    const mape =
      predictions.reduce((sum, row) => sum + Math.abs(row.error / row.actual) * 100, 0) /
      predictions.length;
    return {
      count: predictions.length,
      accuracy:
        (predictions.filter((row) => row.directionMatched).length / predictions.length) * 100,
      mae: absoluteError / predictions.length,
      baselineMae: baselineError / predictions.length,
      mape,
    };
  }, [predictions]);
  const latestPrediction = predictions.at(-1);
  const tradeEvidence = useMemo(() => {
    if (candles.length < 21) return null;
    const recent = candles.slice(-21);
    const previous = recent.slice(0, -1);
    const latest = recent.at(-1)!;
    const support = Math.min(...previous.map((candle) => candle.low));
    const resistance = Math.max(...previous.map((candle) => candle.high));
    const sma20 = recent.slice(-20).reduce((sum, candle) => sum + candle.close, 0) / 20;
    const last50 = candles.slice(-50);
    const sma50 =
      last50.length === 50 ? last50.reduce((sum, candle) => sum + candle.close, 0) / 50 : null;
    const averageVolume = previous.reduce((sum, candle) => sum + candle.volume, 0) / 20;
    return {
      latest,
      support,
      resistance,
      sma20,
      sma50,
      risk: resistance - support,
      rising: latest.close > sma20 && latest.close > previous[0].close,
      volumeConfirmed: latest.volume > averageVolume,
    };
  }, [candles]);

  const financialRows =
    period === "quarterly"
      ? detail.quarters.map((q) => ({
          label: q.quarter,
          Revenue: Math.round(q.revenue / crore),
          "Net profit": Math.round(q.profit / crore),
        }))
      : detail.years.map((y) => ({
          label: y.year,
          Revenue: Math.round(y.revenue / crore),
          "Net profit": Math.round(y.profit / crore),
        }));

  return (
    <Page>
      <PageHeader
        crumbs={[{ label: "Companies", to: "/v2/companies/" }, { label: company.name }]}
        title={company.name}
        meta={
          <>
            <SymbolChip symbol={company.symbol} />
            <SymbolChip symbol={detail.bseCode} exchange="BSE" />
            <StatusBadge tone="neutral" size="xs">
              {company.sector}
            </StatusBadge>
          </>
        }

        description={
          <Group gap={10} wrap="wrap" component="span">
            <Text component="span" size="xl" fw={700} className="kv2-num" c="var(--kv2-text)">
              {formatInr(company.last)}
            </Text>
            <Delta value={change} kind="points" />
            <Delta value={company.changePct} />
            <FreshnessTag state="delayed" detail="sample snapshot" />
          </Group>
        }
        actions={
          <>
            <Button
              variant="default"
              leftSection={<LuBookmarkPlus size={14} />}
              onClick={() =>
                notifications.show({
                  title: "Added to watchlist",
                  message: `${company.symbol} (sample) is now watched.`,
                })
              }
            >
              Watch
            </Button>
            <Button
              variant="default"
              component="a"
              href="https://example.com/"
              target="_blank"
              rel="noreferrer"
              rightSection={<LuExternalLink size={14} />}
            >
              Screener
            </Button>
          </>
        }
      />

      <Stack gap={16}>
        <KpiGrid cols={5}>
          <KpiTile
            label="Prev close"
            value={formatInr(detail.prevClose)}
            hint={`Vol ${formatCompactInr(company.volume).replace("₹", "")} shares`}
          />
          <KpiTile
            label="Engine outlook"
            info="Next-session direction from the engine's sample model. Score is signal strength out of 10; it is not a recommendation."
            value={<DirectionBadge direction={detail.outlook.direction} />}
            hint={`Target ${formatInr(detail.outlook.target)}`}
            delta={<StrengthMeter score={detail.outlook.score} />}
          />
          <KpiTile
            label="News sentiment"
            info="Average score of the last 30 days of scored articles, from −1 (negative) to +1 (positive)."
            value={<SentimentPill score={s.score} />}
            hint={`${s.positive} pos · ${s.neutral} neu · ${s.negative} neg`}
            delta={
              <div style={{ width: 120 }}>
                <SentimentBar positive={s.positive} neutral={s.neutral} negative={s.negative} />
              </div>
            }
          />
          <KpiTile
            label="Valuation"
            info="Compares P/E, P/B and EV/EBITDA with the sector median. Within ±10% counts as in line."
            value={<StatusBadge tone={valuationTone[valuationState]}>{valuationState}</StatusBadge>}
            hint={`${comparableCount} of 3 multiples comparable`}
          />
          <KpiTile
            label="Momentum score"
            info="Sample 20- and 50-session trend blend, scaled from 0 to 10. Historical prices only."
            value={`${formatNumber(detail.momentum, 1)} / 10`}
            delta={<StrengthMeter score={detail.momentum} />}
            hint="Sample trend indicator"
          />
        </KpiGrid>

        <Tabs value={tab} onChange={setTab} keepMounted={false}>
          <Tabs.List style={{ overflowX: "auto", flexWrap: "nowrap" }}>
            <Tabs.Tab value="overview">Overview</Tabs.Tab>
            <Tabs.Tab value="signals">Signals &amp; Review</Tabs.Tab>
            <Tabs.Tab value="financials">Fundamentals &amp; Valuation</Tabs.Tab>
            <Tabs.Tab
              value="news"
              rightSection={<StatusBadge size="xs">{detail.news.length}</StatusBadge>}
            >
              Scored News
            </Tabs.Tab>
            <Tabs.Tab value="delivery">Delivery &amp; volume</Tabs.Tab>
            <Tabs.Tab
              value="ipos"
              rightSection={<StatusBadge size="xs">{detail.ipoScores.length}</StatusBadge>}
            >
              IPO History
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview" pt={16}>
            <Grid gutter={16} align="start">
              <Grid.Col span={{ base: 12, md: 8 }}>
                <Stack gap={16}>
                  <PriceChartPanel
                    title={`${company.symbol} · Daily`}
                    candles={candles}
                    last={company.last}
                  />
                  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing={12}>
                    <KpiTile
                      label="52-week range"
                      value={`${formatInr(detail.week52Low)} – ${formatInr(detail.week52High)}`}
                    />
                    <KpiTile
                      label="Beta"
                      info="How much the price moves relative to Sample Index 50. Below 1 means less volatile."
                      value={detail.beta.toFixed(2)}
                    />
                    <KpiTile
                      label="Delivery"
                      info="Share of traded quantity taken into demat, not squared off intraday."
                      value={`${formatNumber(company.deliveryPct, 1)}%`}
                      hint={`20D avg ${formatNumber(avgDelivery, 1)}%`}
                    />
                  </SimpleGrid>
                  <Panel title={`About ${company.name}`}>
                    <Stack gap={10}>
                      <Text size="sm">{detail.about}</Text>
                      <DescriptionList
                        items={[
                          ["Founded", String(detail.founded)],
                          ["Headquarters", detail.hq],
                          ["Employees", formatNumber(detail.employees)],
                          ["ISIN", <span className="kv2-mono">{detail.isin}</span>],
                          ["Data from", formatDate(detail.dataFrom)],
                        ]}
                      />
                    </Stack>
                  </Panel>
                </Stack>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Panel
                  title="Live depth & quote"
                  info="Fictional saved quote and five-level order book. No live market connection."
                  flush
                >
                  <Stack gap={12} p="md">
                    <Group justify="space-between" align="flex-start" wrap="nowrap">
                      <Stack gap={2}>
                        <Text size="xs" c="dimmed">
                          Last traded
                        </Text>
                        <Text size="xl" fw={700} className="kv2-num">
                          {formatInr(company.last)}
                        </Text>
                      </Stack>
                      <Delta value={company.changePct} />
                    </Group>
                    <SimpleGrid cols={2} spacing={8}>
                      <KpiTile label="Open" value={formatInr(detail.open)} />
                      <KpiTile label="Prev close" value={formatInr(detail.prevClose)} />
                      <KpiTile label="Average price" value={formatInr(detail.averagePrice)} />
                      <KpiTile label="Volume" value={formatNumber(company.volume)} />
                    </SimpleGrid>
                    <Stack gap={4}>
                      <Group justify="space-between">
                        <Text size="xs" fw={600}>
                          Buy / sell quantity
                        </Text>
                        <Text size="xs" c="dimmed">
                          {formatNumber(detail.totalBuyQty)} / {formatNumber(detail.totalSellQty)}
                        </Text>
                      </Group>
                      <Progress.Root size={7} aria-label="Buy and sell quantity ratio">
                        <Progress.Section value={buyPressurePct} color="var(--kv2-gain)" />
                        <Progress.Section value={100 - buyPressurePct} color="var(--kv2-loss)" />
                      </Progress.Root>
                    </Stack>
                    <div className="kv2-table-wrap">
                      <Table aria-label="Market depth (top 5)">
                        <Table.Thead>
                          <Table.Tr>
                            <Table.Th>Level</Table.Th>
                            <Table.Th data-align="right">Bid qty</Table.Th>
                            <Table.Th data-align="right">Bid price</Table.Th>
                            <Table.Th data-align="right">Ask price</Table.Th>
                            <Table.Th data-align="right">Ask qty</Table.Th>
                          </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                          {marketDepthRows(detail.marketDepth).map((level) => (
                            <Table.Tr key={level.level}>
                              <Table.Td>{level.level}</Table.Td>
                              <Table.Td data-align="right" className="kv2-num">
                                {formatNumber(level.bidQty)}
                              </Table.Td>
                              <Table.Td data-align="right" className="kv2-num">
                                {formatInr(level.bidPrice)}
                              </Table.Td>
                              <Table.Td data-align="right" className="kv2-num">
                                {formatInr(level.askPrice)}
                              </Table.Td>
                              <Table.Td data-align="right" className="kv2-num">
                                {formatNumber(level.askQty)}
                              </Table.Td>
                            </Table.Tr>
                          ))}
                        </Table.Tbody>
                      </Table>
                    </div>
                    <Accordion variant="default" styles={{ content: { paddingInline: 0 } }}>
                      <Accordion.Item value="key-stats">
                        <Accordion.Control>Key stats</Accordion.Control>
                        <Accordion.Panel>
                          <DescriptionList
                            items={[
                              [
                                "Day range",
                                <span className="kv2-num">{`${formatInr(detail.low)} – ${formatInr(detail.high)}`}</span>,
                              ],
                              [
                                "Market cap",
                                <span className="kv2-num">
                                  {formatCompactInr(company.marketCap)}
                                </span>,
                              ],
                              [
                                "P/E",
                                <span className="kv2-num">{formatNumber(company.pe, 1)}×</span>,
                              ],
                              [
                                "P/B",
                                <span className="kv2-num">{formatNumber(detail.pb, 2)}×</span>,
                              ],
                              [
                                "Book value",
                                <span className="kv2-num">{formatInr(detail.bookValue)}</span>,
                              ],
                              [
                                "Dividend yield",
                                <span className="kv2-num">
                                  {formatPercent(detail.dividendYield, { signed: false })}
                                </span>,
                              ],
                            ]}
                          />
                        </Accordion.Panel>
                      </Accordion.Item>
                    </Accordion>
                  </Stack>
                </Panel>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="financials" pt={16}>
            <Stack gap={16}>
              <Grid gutter={16}>
                <Grid.Col span={{ base: 12, md: 8 }}>
                  <Panel
                    title="Revenue & net profit"
                    info="Figures in ₹ crore. Sample numbers derived from market cap and P/E."
                    actions={
                      <SegmentedControl
                        size="xs"
                        value={period}
                        onChange={setPeriod}
                        data={[
                          { value: "quarterly", label: "Quarterly" },
                          { value: "annual", label: "Annual" },
                        ]}
                      />
                    }
                  >
                    <BarChart
                      h={240}
                      data={financialRows}
                      dataKey="label"
                      series={[
                        { name: "Revenue", color: "indigo.6" },
                        { name: "Net profit", color: "emerald.6" },
                      ]}
                      valueFormatter={(v) => `₹${formatNumber(v)} Cr`}
                      withLegend
                      gridAxis="y"
                    />
                  </Panel>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Panel title="Shareholding" info="Latest sample quarter, % of total shares.">
                    <Stack align="center" gap={12}>
                      <DonutChart
                        data={detail.shareholding}
                        size={150}
                        thickness={20}
                        withTooltip
                        tooltipDataSource="segment"
                        valueFormatter={(v) => `${v}%`}
                      />
                      <Stack gap={4} w="100%">
                        {detail.shareholding.map((h) => (
                          <Group key={h.name} justify="space-between">
                            <Text size="xs">{h.name}</Text>
                            <Text size="xs" className="kv2-num" fw={600}>
                              {h.value}%
                            </Text>
                          </Group>
                        ))}
                      </Stack>
                    </Stack>
                  </Panel>
                </Grid.Col>
              </Grid>

              <Panel
                title="Is this company overvalued?"
                info="Each multiple is compared with the sector median. Within ±10% is in line; higher is a premium, lower a discount."
                actions={
                  <StatusBadge tone={valuationTone[valuationState]}>{valuationState}</StatusBadge>
                }
                flush
              >
                <div className="kv2-table-wrap">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Multiple</Table.Th>
                        <Table.Th data-align="right">Company</Table.Th>
                        <Table.Th data-align="right">Sector</Table.Th>
                        <Table.Th>Comparison</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {valuationRows.map((m) => {
                        const diff = m.difference;
                        const tone: Tone = !m.comparable
                          ? "neutral"
                          : Math.abs(diff!) <= 10
                            ? "info"
                            : diff! > 0
                              ? "caution"
                              : "gain";
                        return (
                          <Table.Tr key={m.name}>
                            <Table.Td>
                              <Group gap={4}>
                                {m.name}
                                <InfoTip>{m.info}</InfoTip>
                              </Group>
                            </Table.Td>
                            <Table.Td data-align="right" className="kv2-num">
                              {m.comparable ? `${formatNumber(m.company, 1)}×` : "Not available"}
                            </Table.Td>
                            <Table.Td data-align="right" className="kv2-num">
                              {m.comparable ? `${formatNumber(m.sector, 1)}×` : "Not available"}
                            </Table.Td>
                            <Table.Td>
                              <StatusBadge tone={tone} size="xs">
                                {diff === null
                                  ? "Not comparable"
                                  : Math.abs(diff) <= 10
                                    ? "In line"
                                    : `${formatPercent(diff, { decimals: 0 })} ${diff > 0 ? "premium" : "discount"}`}
                              </StatusBadge>
                            </Table.Td>
                          </Table.Tr>
                        );
                      })}
                    </Table.Tbody>
                  </Table>
                </div>
                <Text size="xs" c="dimmed" p="md">
                  Saved sample values · not live. Premium/discount compares each positive multiple
                  with its sample sector value. Opposing comparisons are mixed; missing or
                  non-positive values are not comparable. This is not a fair-value estimate or
                  recommendation.
                </Text>
                <Accordion variant="separated" mx="md" mb="md">
                  <Accordion.Item value="valuation-method">
                    <Accordion.Control>How to read this valuation</Accordion.Control>
                    <Accordion.Panel>
                      Premium/discount = (company multiple ÷ sector multiple − 1) × 100. Opposing
                      comparisons are mixed. No ratios are averaged into a fair-value price, and a
                      lower multiple is not proof of undervaluation.
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              </Panel>

              <Panel title="Quarterly results" info="₹ crore unless noted. Sample figures." flush>
                <div className="kv2-table-wrap">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Quarter</Table.Th>
                        <Table.Th data-align="right">Revenue</Table.Th>
                        <Table.Th data-align="right">EBITDA</Table.Th>
                        <Table.Th data-align="right">Net profit</Table.Th>
                        <Table.Th data-align="right">Net margin</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {detail.quarters.map((q) => (
                        <Table.Tr key={q.quarter}>
                          <Table.Td>{q.quarter}</Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(q.revenue / crore)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(q.ebitda / crore)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(q.profit / crore)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatPercent(q.margin, { signed: false, decimals: 1 })}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </div>
              </Panel>

              <Panel
                title="Annual summary"
                info="Return on equity (ROE) = net profit ÷ shareholders' equity."
                flush
              >
                <div className="kv2-table-wrap">
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Year</Table.Th>
                        <Table.Th data-align="right">Revenue</Table.Th>
                        <Table.Th data-align="right">Net profit</Table.Th>
                        <Table.Th data-align="right">EPS (₹)</Table.Th>
                        <Table.Th data-align="right">ROE</Table.Th>
                        <Table.Th data-align="right">Debt / equity</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {detail.years.map((y) => (
                        <Table.Tr key={y.year}>
                          <Table.Td>{y.year}</Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(y.revenue / crore)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(y.profit / crore)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatNumber(y.eps, 2)}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {formatPercent(y.roe, { signed: false, decimals: 1 })}
                          </Table.Td>
                          <Table.Td data-align="right" className="kv2-num">
                            {y.debtEquity.toFixed(2)}
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </div>
              </Panel>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="signals" pt={16}>
            <Stack gap={16}>
              <Panel
                title="Prediction accuracy & deviations"
                info="A historical simulation from fictional sample closes, not the engine's live track record."
                actions={
                  <Select
                    aria-label="Forecast horizon"
                    value={String(horizon)}
                    onChange={(value) => value && setHorizon(Number(value))}
                    data={[
                      { value: "1", label: "Next session" },
                      { value: "5", label: "5 sessions" },
                      { value: "20", label: "20 sessions" },
                    ]}
                    w={150}
                    size="xs"
                  />
                }
              >
                {predictionSummary ? (
                  <Stack gap={12}>
                    <Alert
                      color={
                        predictionSummary.mae < predictionSummary.baselineMae ? "teal" : "orange"
                      }
                      title={
                        predictionSummary.mae < predictionSummary.baselineMae
                          ? "Lower price error than a no-change baseline"
                          : "No improvement over a no-change baseline"
                      }
                    >
                      {predictionSummary.count} sample comparisons. Future dashed values and
                      historical simulations are not verified predictions.
                    </Alert>
                    <KpiGrid cols={3}>
                      <KpiTile
                        label="Direction correct"
                        value={`${formatNumber(predictionSummary.accuracy, 1)}%`}
                        hint={`${predictions.filter((row) => row.directionMatched).length} of ${predictionSummary.count} matched`}
                        delta={
                          <Progress
                            value={predictionSummary.accuracy}
                            size={5}
                            aria-label={`Direction correct ${formatNumber(predictionSummary.accuracy, 1)}%`}
                          />
                        }
                      />
                      <KpiTile
                        label="Average price miss"
                        value={formatInr(predictionSummary.mae)}
                        hint={`${formatNumber(predictionSummary.mape, 2)}% average error`}
                      />
                      <KpiTile
                        label="No-change baseline miss"
                        value={formatInr(predictionSummary.baselineMae)}
                        hint="Uses origin close as the price guess"
                      />
                    </KpiGrid>
                    {latestPrediction ? (
                      <Panel title={`Latest comparison · ${formatDate(latestPrediction.target)}`}>
                        <Stack gap={8}>
                          <Group gap={8} wrap="wrap">
                            <StatusBadge tone={latestPrediction.directionMatched ? "gain" : "loss"}>
                              {latestPrediction.directionMatched
                                ? "Direction matched"
                                : "Direction missed"}
                            </StatusBadge>
                            <Text size="xs" c="dimmed">
                              Projected {formatInr(latestPrediction.predicted)} · Actual{" "}
                              {formatInr(latestPrediction.actual)} · Difference{" "}
                              {formatSigned(latestPrediction.error)} INR
                            </Text>
                          </Group>
                          <Text size="xs" c="dimmed">
                            Related news is possible context only, not a confirmed cause:{" "}
                            {detail.news[0]?.title ?? "No sample article available"}.
                          </Text>
                        </Stack>
                      </Panel>
                    ) : null}
                    <Accordion variant="separated">
                      <Accordion.Item value="deviations">
                        <Accordion.Control>
                          Projection deviations &amp; sample comparisons ({predictions.length})
                        </Accordion.Control>
                        <Accordion.Panel>
                          <div className="kv2-table-wrap">
                            <Table>
                              <Table.Thead>
                                <Table.Tr>
                                  <Table.Th>Origin</Table.Th>
                                  <Table.Th>Target</Table.Th>
                                  <Table.Th data-align="right">Projected</Table.Th>
                                  <Table.Th data-align="right">Actual</Table.Th>
                                  <Table.Th data-align="right">Difference</Table.Th>
                                  <Table.Th>Direction</Table.Th>
                                </Table.Tr>
                              </Table.Thead>
                              <Table.Tbody>
                                {[...predictions]
                                  .reverse()
                                  .slice(0, 12)
                                  .map((row) => (
                                    <Table.Tr key={`${row.origin}-${row.target}`}>
                                      <Table.Td>{formatDate(row.origin)}</Table.Td>
                                      <Table.Td>{formatDate(row.target)}</Table.Td>
                                      <Table.Td data-align="right" className="kv2-num">
                                        {formatInr(row.predicted)}
                                      </Table.Td>
                                      <Table.Td data-align="right" className="kv2-num">
                                        {formatInr(row.actual)}
                                      </Table.Td>
                                      <Table.Td data-align="right" className="kv2-num">
                                        {formatSigned(row.error)}
                                      </Table.Td>
                                      <Table.Td>
                                        <StatusBadge
                                          tone={row.directionMatched ? "gain" : "loss"}
                                          size="xs"
                                        >
                                          {row.directionMatched ? "Matched" : "Missed"}
                                        </StatusBadge>
                                      </Table.Td>
                                    </Table.Tr>
                                  ))}
                              </Table.Tbody>
                            </Table>
                          </div>
                        </Accordion.Panel>
                      </Accordion.Item>
                    </Accordion>
                    <Text size="xs" c="dimmed">
                      Direction accuracy and price error are calculated from the sample history
                      shown; no saved forecast record or real outcome is represented.
                    </Text>
                  </Stack>
                ) : (
                  <EmptyState
                    title="Not enough history"
                    description="No comparisons can be computed for this horizon."
                  />
                )}
              </Panel>

              <Panel
                title="Saved engine outlook"
                info="The original product records direction, strength, target date, and model inputs. This preview shows sample-only placeholders."
              >
                <Stack gap={12}>
                  <Group gap={10} wrap="wrap">
                    <DirectionBadge direction={detail.outlook.direction} />
                    <Text size="sm">
                      Current sample outlook · target {formatInr(detail.outlook.target)}
                    </Text>
                    <StrengthMeter score={detail.outlook.score} />
                  </Group>
                  <DescriptionList
                    items={[
                      ["Momentum input", `${formatNumber(detail.momentum, 1)} / 10`],
                      [
                        "News input",
                        `${formatSigned(s.score)} · ${s.positive} positive / ${s.neutral} neutral / ${s.negative} negative`,
                      ],
                      ["Data status", "Fictional snapshot · not live"],
                    ]}
                  />
                  <Accordion variant="separated">
                    <Accordion.Item value="saved-outlook-records">
                      <Accordion.Control>
                        Sample historical outcome checks ({predictions.length})
                      </Accordion.Control>
                      <Accordion.Panel>
                        <Text size="xs" c="dimmed" mb="sm">
                          These rows are generated from fictional price history to demonstrate the
                          review layout. No production prediction records are shown.
                        </Text>
                        <div className="kv2-table-wrap">
                          <Table>
                            <Table.Thead>
                              <Table.Tr>
                                <Table.Th>Origin</Table.Th>
                                <Table.Th>Target</Table.Th>
                                <Table.Th>Sample direction</Table.Th>
                                <Table.Th data-align="right">Strength</Table.Th>
                                <Table.Th>Outcome</Table.Th>
                              </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                              {[...predictions]
                                .reverse()
                                .slice(0, 8)
                                .map((row) => {
                                  const direction =
                                    row.predicted > row.originClose
                                      ? "up"
                                      : row.predicted < row.originClose
                                        ? "down"
                                        : "flat";
                                  const strength = Math.min(
                                    9.5,
                                    4 +
                                      (Math.abs(row.predicted - row.originClose) /
                                        row.originClose) *
                                        100,
                                  );
                                  return (
                                    <Table.Tr key={`saved-${row.origin}-${row.target}`}>
                                      <Table.Td>{formatDate(row.origin)}</Table.Td>
                                      <Table.Td>{formatDate(row.target)}</Table.Td>
                                      <Table.Td>
                                        <DirectionBadge direction={direction} />
                                      </Table.Td>
                                      <Table.Td data-align="right" className="kv2-num">
                                        {formatNumber(strength, 1)} / 10
                                      </Table.Td>
                                      <Table.Td>
                                        <StatusBadge
                                          tone={row.directionMatched ? "gain" : "loss"}
                                          size="xs"
                                        >
                                          {row.directionMatched ? "Matched" : "Missed"}
                                        </StatusBadge>
                                      </Table.Td>
                                    </Table.Tr>
                                  );
                                })}
                            </Table.Tbody>
                          </Table>
                        </div>
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                </Stack>
              </Panel>

              <Panel
                title="Trade setup watchlist"
                info="Conditional examples calculated from saved sample OHLCV history, not investment advice."
                flush
              >
                {tradeEvidence ? (
                  <Stack gap={12} p="md">
                    <Alert color="orange" title="Sample history freshness is not verified">
                      This mock page cannot confirm whether saved candles are recent or whether a
                      quoted price is executable.
                    </Alert>
                    <Text size="sm">
                      As of {formatDate(tradeEvidence.latest.date)}: close{" "}
                      <span className="kv2-num">{formatInr(tradeEvidence.latest.close)}</span>, SMA
                      20 <span className="kv2-num">{formatInr(tradeEvidence.sma20)}</span>
                      {tradeEvidence.sma50 !== null ? (
                        <>
                          {" "}
                          and SMA 50{" "}
                          <span className="kv2-num">{formatInr(tradeEvidence.sma50)}</span>
                        </>
                      ) : null}
                      . Prior 20-session low/high: {formatInr(tradeEvidence.support)} /{" "}
                      {formatInr(tradeEvidence.resistance)}. Latest volume{" "}
                      {tradeEvidence.volumeConfirmed ? "exceeds" : "does not exceed"} the prior
                      20-session average.
                    </Text>
                    <div className="kv2-table-wrap">
                      <Table>
                        <Table.Thead>
                          <Table.Tr>
                            <Table.Th>Style</Table.Th>
                            <Table.Th>State &amp; rationale</Table.Th>
                            <Table.Th>Condition &amp; risk plan</Table.Th>
                          </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                          <Table.Tr>
                            <Table.Td>Swing long · days to weeks</Table.Td>
                            <Table.Td>
                              <StatusBadge
                                tone={tradeEvidence.rising ? "gain" : "neutral"}
                                size="xs"
                              >
                                {tradeEvidence.rising
                                  ? "Watch for confirmation"
                                  : "Wait / no long setup"}
                              </StatusBadge>
                              <Text size="xs" c="dimmed" mt={4}>
                                {tradeEvidence.rising
                                  ? "Close is above SMA 20 with positive 20-session momentum."
                                  : "Trend and momentum do not both support a long setup."}
                              </Text>
                            </Table.Td>
                            <Table.Td>
                              Watch only after a completed daily close above{" "}
                              {formatInr(tradeEvidence.resistance)} with above-average volume. If
                              already above, do not chase; reassess a retest. Illustrative
                              invalidation below {formatInr(tradeEvidence.support)} gives risk of{" "}
                              {formatInr(tradeEvidence.risk)} per share (
                              {formatNumber(
                                (tradeEvidence.risk / tradeEvidence.resistance) * 100,
                                1,
                              )}
                              %); a 2R arithmetic level is{" "}
                              {formatInr(tradeEvidence.resistance + 2 * tradeEvidence.risk)}, not a
                              predicted target.
                            </Table.Td>
                          </Table.Tr>
                          <Table.Tr>
                            <Table.Td>Positional long · weeks to months</Table.Td>
                            <Table.Td>
                              <StatusBadge tone="neutral" size="xs">
                                {tradeEvidence.sma50 === null
                                  ? "Need 50 sessions"
                                  : tradeEvidence.rising &&
                                      tradeEvidence.sma20 > tradeEvidence.sma50
                                    ? "Trend-aligned watch"
                                    : "Wait / trend not aligned"}
                              </StatusBadge>
                            </Table.Td>
                            <Table.Td>
                              Require close &gt; SMA 20 &gt; SMA 50, then reassess after a confirmed
                              breakout or supported pullback. Review fundamentals and liquidity.
                            </Table.Td>
                          </Table.Tr>
                          <Table.Tr>
                            <Table.Td>Intraday / short selling</Table.Td>
                            <Table.Td>
                              <StatusBadge tone="neutral" size="xs">
                                Not assessable
                              </StatusBadge>
                            </Table.Td>
                            <Table.Td>
                              Daily sample data cannot establish intraday entries, spreads,
                              execution liquidity, or short eligibility.
                            </Table.Td>
                          </Table.Tr>
                        </Table.Tbody>
                      </Table>
                    </div>
                    <Text size="xs" c="dimmed">
                      Illustrative scenarios only. The history is not live or backtested; gaps,
                      fees, slippage, and actual entry prices can materially change risk.
                    </Text>
                  </Stack>
                ) : (
                  <EmptyState
                    title="Wait / insufficient data"
                    description="At least 21 valid daily sample sessions are needed to calculate setup examples."
                  />
                )}
              </Panel>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="news" pt={16}>
            <Panel
              flush
              title="Scored news"
              info="Each article is scored from −1 to +1 for its likely effect on this company. Relevance is how directly the article is about the company."
              actions={
                <Group gap={6} visibleFrom="sm">
                  <StatusBadge tone="gain" size="xs">
                    ▲ {s.positive} positive
                  </StatusBadge>
                  <StatusBadge tone="neutral" size="xs">
                    – {s.neutral} neutral
                  </StatusBadge>
                  <StatusBadge tone="loss" size="xs">
                    ▼ {s.negative} negative
                  </StatusBadge>
                </Group>
              }
            >
              <DataTable
                columns={newsColumns}
                rows={news}
                rowKey={(n) => n.id}
                totalLabel="articles"
                toolbar={
                  <Group gap={8} w="100%">
                    <Select
                      aria-label="Sentiment"
                      placeholder="Any sentiment"
                      data={[
                        { value: "positive", label: "▲ Positive" },
                        { value: "neutral", label: "– Neutral" },
                        { value: "negative", label: "▼ Negative" },
                      ]}
                      value={newsSentiment}
                      onChange={setNewsSentiment}
                      clearable
                      w={{ base: "100%", sm: 180 }}
                    />
                    <Select
                      aria-label="Source"
                      placeholder="Any source"
                      data={[...new Set(detail.news.map((article) => article.source))]}
                      value={newsSource}
                      onChange={setNewsSource}
                      clearable
                      w={{ base: "100%", sm: 180 }}
                    />
                    {newsSource || newsSentiment ? (
                      <Button
                        size="xs"
                        variant="subtle"
                        onClick={() => {
                          setNewsSource(null);
                          setNewsSentiment(null);
                        }}
                      >
                        Clear filters
                      </Button>
                    ) : null}
                    <Text size="xs" c="dimmed" ml="auto">
                      {news.length} of {detail.news.length} articles ·{" "}
                      <Anchor component={AppLink} href="/v2/news/" size="xs">
                        All news
                      </Anchor>
                    </Text>
                  </Group>
                }
                empty={
                  <EmptyState
                    title="No articles"
                    description="No sample articles match this sentiment."
                  />
                }
              />
            </Panel>
          </Tabs.Panel>

          <Tabs.Panel value="ipos" pt={16}>
            <Stack gap={12}>
              <Alert color="gray" title="Sample IPO score history">
                All scores and inputs below are fictional placeholders. Grey market premium is
                unofficial and indicative only.
              </Alert>
              {detail.ipoScores.map((ipo) => (
                <Panel
                  key={ipo.id}
                  title={ipo.name}
                  info={`Sample score saved ${ipo.scoredAt}. This is not investment advice.`}
                  actions={
                    <Group gap={6}>
                      <StatusBadge
                        tone={
                          ipo.verdict === "positive"
                            ? "gain"
                            : ipo.verdict === "avoid"
                              ? "loss"
                              : "neutral"
                        }
                        size="xs"
                      >
                        {ipo.verdict}
                      </StatusBadge>
                      <StatusBadge tone="info" size="xs">
                        Score {formatSigned(ipo.score)}
                      </StatusBadge>
                    </Group>
                  }
                >
                  <Accordion variant="separated">
                    <Accordion.Item value={`inputs-${ipo.id}`}>
                      <Accordion.Control>All IPO scoring inputs</Accordion.Control>
                      <Accordion.Panel>
                        <div className="kv2-table-wrap">
                          <Table>
                            <Table.Thead>
                              <Table.Tr>
                                <Table.Th>Signal</Table.Th>
                                <Table.Th>Value</Table.Th>
                                <Table.Th data-align="right">Signal score</Table.Th>
                                <Table.Th>Notes</Table.Th>
                              </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                              {ipo.inputs.map((input) => (
                                <Table.Tr key={input.name}>
                                  <Table.Td>{input.name}</Table.Td>
                                  <Table.Td>{input.value}</Table.Td>
                                  <Table.Td data-align="right" className="kv2-num">
                                    {formatSigned(input.score)}
                                  </Table.Td>
                                  <Table.Td>{input.note}</Table.Td>
                                </Table.Tr>
                              ))}
                            </Table.Tbody>
                          </Table>
                        </div>
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                </Panel>
              ))}
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="delivery" pt={16}>
            <Stack gap={16}>
              <KpiGrid cols={4}>
                <KpiTile
                  label="Latest delivery %"
                  value={`${formatNumber(latestDelivery.deliveryPct, 1)}%`}
                  delta={
                    <Delta
                      value={latestDelivery.deliveryPct - avgDelivery}
                      kind="points"
                      decimals={1}
                      size="xs"
                    />
                  }
                  hint="vs 20D average"
                />
                <KpiTile label="20D avg delivery %" value={`${formatNumber(avgDelivery, 1)}%`} />
                <KpiTile
                  label="Avg traded qty"
                  value={formatNumber(
                    detail.delivery.reduce((sum, d) => sum + d.volume, 0) / detail.delivery.length,
                  )}
                  hint="shares / session"
                />
                <KpiTile
                  label="Volume signal"
                  info="Accumulation: delivery % above average on up days. Distribution: above average on down days."
                  value={
                    <StatusBadge
                      tone={
                        company.signal === "Accumulation"
                          ? "gain"
                          : company.signal === "Distribution"
                            ? "loss"
                            : "neutral"
                      }
                    >
                      {company.signal}
                    </StatusBadge>
                  }
                />
              </KpiGrid>
              <Grid gutter={16}>
                <Grid.Col span={{ base: 12, md: 8 }}>
                  <Panel
                    title="Delivered vs intraday quantity"
                    info="Thousands of shares per session. Delivered shares were taken into demat; intraday shares were squared off the same day."
                  >
                    <BarChart
                      h={240}
                      type="stacked"
                      data={deliveryChart}
                      dataKey="date"
                      withLegend
                      series={[
                        { name: "Delivered", color: "indigo.6" },
                        { name: "Intraday", color: "slate.4" },
                      ]}
                      valueFormatter={(v) => `${formatNumber(v)}k`}
                      gridAxis="y"
                    />
                  </Panel>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Panel
                    title="Delivery % trend"
                    info="The reference line marks the 20-session average."
                  >
                    <LineChart
                      h={240}
                      data={deliveryChart}
                      dataKey="date"
                      series={[{ name: "Delivery %", color: "amber.6" }]}
                      referenceLines={[
                        { y: Number(avgDelivery.toFixed(1)), label: "20D avg", color: "slate.5" },
                      ]}
                      yAxisProps={{ domain: [0, 100] }}
                      valueFormatter={(v) => `${formatNumber(v, 1)}%`}
                      curveType="monotone"
                      withDots={false}
                      gridAxis="y"
                    />
                  </Panel>
                </Grid.Col>
              </Grid>
              <Panel flush title="Daily delivery data">
                <DataTable
                  columns={deliveryColumns}
                  rows={[...detail.delivery].reverse()}
                  rowKey={(d) => d.date}
                  totalLabel="sessions"
                />
              </Panel>
              <Muted>
                Delivery data is published after market close. Change in delivery % is shown in
                percentage points ({formatSigned(latestDelivery.deliveryPct - avgDelivery, 1)} pts
                today).
              </Muted>
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Page>
  );
}

export { CompanyDetailPage } from "./DataDriven";
