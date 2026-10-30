import { BarChart, DonutChart, LineChart } from "@mantine/charts";
import {
  Anchor,
  Button,
  Grid,
  Group,
  Progress,
  SegmentedControl,
  Select,
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
import type { CompanyNews, DeliveryDay } from "../mock/companies";
import { mockCandles } from "../mock/generate";

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

export function CompanyDetailPage({ id }: { id: string }) {
  const company = findCompany(id);
  const detail = useMemo(() => companyDetail(company), [company]);
  const candles = useMemo(() => mockCandles(260, company.last, companySeed(company)), [company]);
  const [tab, setTab] = useState<string | null>("overview");
  const [period, setPeriod] = useState("quarterly");
  const [newsSentiment, setNewsSentiment] = useState<string | null>(null);

  const change = company.last - detail.prevClose;
  const s = detail.sentiment;
  const comparable = detail.multiples.filter(
    (m) => Math.abs(m.company / m.sector - 1) <= 0.1,
  ).length;

  const news = detail.news.filter(
    (n) =>
      !newsSentiment ||
      (newsSentiment === "positive" && n.score >= 0.15) ||
      (newsSentiment === "negative" && n.score <= -0.15) ||
      (newsSentiment === "neutral" && Math.abs(n.score) < 0.15),
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
            <FreshnessTag state="live" detail="11:42 IST" />
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
            value={
              <StatusBadge tone={valuationTone[detail.valuation]}>{detail.valuation}</StatusBadge>
            }
            hint={`${comparable} of 3 multiples in line`}
          />
          <KpiTile
            label="Delivery %"
            info="Share of traded quantity taken into demat (not squared off intraday). High delivery on up days suggests accumulation."
            value={`${formatNumber(company.deliveryPct, 1)}%`}
            hint={`20D avg ${formatNumber(avgDelivery, 1)}%`}
          />
        </KpiGrid>

        <Tabs value={tab} onChange={setTab} keepMounted={false}>
          <Tabs.List style={{ overflowX: "auto", flexWrap: "nowrap" }}>
            <Tabs.Tab value="overview">Overview</Tabs.Tab>
            <Tabs.Tab value="financials">Financials</Tabs.Tab>
            <Tabs.Tab
              value="news"
              rightSection={<StatusBadge size="xs">{detail.news.length}</StatusBadge>}
            >
              News
            </Tabs.Tab>
            <Tabs.Tab value="delivery">Delivery & volume</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview" pt={16}>
            <Grid gutter={16}>
              <Grid.Col span={{ base: 12, md: 8 }}>
                <Stack gap={16}>
                  <PriceChartPanel
                    title={`${company.symbol} · Daily`}
                    candles={candles}
                    last={company.last}
                  />
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
                <Stack gap={16}>
                  <Panel
                    title="Key stats"
                    info="Sample figures for today's session and the trailing 12 months."
                  >
                    <DescriptionList
                      items={[
                        ["Open", <span className="kv2-num">{formatInr(detail.open)}</span>],
                        [
                          "Day range",
                          <span className="kv2-num">{`${formatInr(detail.low)} – ${formatInr(detail.high)}`}</span>,
                        ],
                        [
                          "52W range",
                          <span className="kv2-num">{`${formatInr(detail.week52Low)} – ${formatInr(detail.week52High)}`}</span>,
                        ],
                        [
                          "Market cap",
                          <span className="kv2-num">{formatCompactInr(company.marketCap)}</span>,
                        ],
                        ["P/E", <span className="kv2-num">{formatNumber(company.pe, 1)}×</span>],
                        ["P/B", <span className="kv2-num">{formatNumber(detail.pb, 2)}×</span>],
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
                        [
                          <Group gap={4}>
                            Beta
                            <InfoTip>
                              How much the price moves relative to Sample Index 50. Below 1 means
                              less volatile.
                            </InfoTip>
                          </Group>,
                          <span className="kv2-num">{detail.beta.toFixed(2)}</span>,
                        ],
                        ["Volume", <span className="kv2-num">{formatNumber(company.volume)}</span>],
                      ]}
                    />
                  </Panel>
                  <Panel
                    title="Momentum"
                    info="Blend of 20- and 50-session trend, scaled 0–10. Sample model, not investment advice."
                  >
                    <Stack gap={8}>
                      <StrengthMeter score={detail.momentum} />
                      <Muted>
                        Not investment advice. Scores are computed from historical sample prices
                        only.
                      </Muted>
                    </Stack>
                  </Panel>
                </Stack>
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
                  <StatusBadge tone={valuationTone[detail.valuation]}>
                    {detail.valuation}
                  </StatusBadge>
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
                      {detail.multiples.map((m) => {
                        const diff = (m.company / m.sector - 1) * 100;
                        const tone: Tone =
                          Math.abs(diff) <= 10 ? "info" : diff > 0 ? "caution" : "gain";
                        return (
                          <Table.Tr key={m.name}>
                            <Table.Td>
                              <Group gap={4}>
                                {m.name}
                                <InfoTip>{m.info}</InfoTip>
                              </Group>
                            </Table.Td>
                            <Table.Td data-align="right" className="kv2-num">
                              {formatNumber(m.company, 1)}×
                            </Table.Td>
                            <Table.Td data-align="right" className="kv2-num">
                              {formatNumber(m.sector, 1)}×
                            </Table.Td>
                            <Table.Td>
                              <StatusBadge tone={tone} size="xs">
                                {Math.abs(diff) <= 10
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
