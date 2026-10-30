import {
  Anchor,
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Pagination,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { LuExternalLink, LuRefreshCw } from "react-icons/lu";

import {
  accountQuery,
  createTelegramLink,
  createToken,
  revokeToken,
  sendEmailVerification,
  unlinkTelegram,
  updateDelivery,
} from "../../shared/api/account";
import { calendarQuery } from "../../shared/api/calendar";
import {
  companyQuery,
  companiesQuery,
  companyMarketsQuery,
  companyListRefreshStatusQuery,
  refreshCompanyList,
} from "../../shared/api/companies";
import { deliveryQuery } from "../../shared/api/delivery";
import { exchangeInstrumentsQuery } from "../../shared/api/exchangeInstruments";
import { useLiveQuotes } from "../../shared/api/liveQuotes";
import { marketsQuery } from "../../shared/api/markets";
import { newsQuery } from "../../shared/api/news";
import { ipoQuery, iposQuery } from "../../shared/api/ipos";
import { reportQuery, reportsQuery } from "../../shared/api/reports";
import { auditQuery, runQuery, runsQuery } from "../../shared/api/ops";
import type { AuditSearch, RunSearch } from "../../shared/api/ops";
import { opsPageQuery, opsSearchSchema, submitOpsForm } from "../../shared/api/opsWorkspace";
import type { OpsSearch } from "../../shared/api/opsWorkspace";
import { todayQuery } from "../../shared/api/today";
import { stopRun } from "../../shared/api/ops";
import { csrfToken } from "../../shared/api/client";
import { sessionQuery } from "../../shared/api/session";
import type {
  Account,
  CompanyDetail,
  CompanyItem,
  OpsAuditPage,
  OpsField as OpsFieldData,
  OpsForm as OpsFormData,
  IpoDetail,
  IpoSummary,
  NewsItem,
  OpsCell,
  OpsPage,
  OpsRunDetail,
  OpsRow,
  OpsRunPage,
  ReportDetail,
  ReportSummary,
  Today,
} from "../../shared/api/generated/types.gen";
import {
  AppLink,
  CandlestickChart,
  Delta,
  DirectionBadge,
  EmptyState,
  ErrorState,
  FreshnessTag,
  KpiGrid,
  KpiTile,
  Page,
  PageHeader,
  Panel,
  SkeletonRows,
  StatusBadge,
  StrengthMeter,
  formatDate,
  formatInr,
  formatNumber,
} from "../components";

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Asia/Kolkata",
      }).format(date);
}

function safeDirection(value: string): "up" | "down" | "flat" {
  return value === "up" ? "up" : value === "down" ? "down" : "flat";
}

function QueryState({
  pending,
  error,
  retry,
  children,
}: {
  pending: boolean;
  error: unknown;
  retry: () => void;
  children: ReactNode;
}) {
  if (pending) return <SkeletonRows rows={6} />;
  if (error) return <ErrorState onRetry={retry} />;
  return <>{children}</>;
}

function PageNumber({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}) {
  return pages > 1 ? <Pagination total={pages} value={page} onChange={onChange} size="sm" /> : null;
}

function DataTable<Row>({
  columns,
  rows,
  rowKey,
  empty,
}: {
  columns: Array<{ label: string; render: (row: Row) => ReactNode }>;
  rows: Row[];
  rowKey: (row: Row) => string | number;
  empty: string;
}) {
  if (!rows.length) return <EmptyState title={empty} />;
  return (
    <div style={{ overflowX: "auto" }}>
      <Table striped highlightOnHover withTableBorder={false} miw={640} fz="sm">
        <Table.Thead>
          <Table.Tr>
            {columns.map(({ label }) => (
              <Table.Th key={label}>{label}</Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={rowKey(row)}>
              {columns.map(({ label, render }) => (
                <Table.Td key={label}>{render(row)}</Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </div>
  );
}

const pageSize = 25;

export function TodayPage() {
  const query = useQuery(todayQuery());
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Today"
        description={
          data ? `${formatDate(data.today)} · Your latest saved market brief.` : undefined
        }
        meta={data?.markets ? <FreshnessTag state="delayed" detail="Saved data" /> : undefined}
      />
      <QueryState pending={query.isPending} error={query.error} retry={() => void query.refetch()}>
        {data ? <TodayContent data={data} /> : null}
      </QueryState>
    </Page>
  );
}

function TodayContent({ data }: { data: Today }) {
  const market = data.markets;
  const outlook = market?.outlook;
  const live = useLiveQuotes(data.stocks_watch?.items.map((item) => item.id) ?? []);
  const quoteCards =
    live.indices.length > 0
      ? live.indices.slice(0, 3).map((quote) => ({
          key: quote.key,
          name: quote.name || quote.symbol,
          value: formatInr(quote.ltp),
          delta:
            quote.change_pct === null ? "Change unavailable" : <Delta value={quote.change_pct} />,
          hint: `Live · ${formatTimestamp(quote.as_of)}`,
        }))
      : (market?.quotes ?? []).slice(0, 3).map((quote) => ({
          key: quote.name,
          name: quote.name,
          value: quote.close,
          delta: quote.change,
          hint: `Saved close · ${formatDate(quote.day)}`,
        }));
  return (
    <Stack gap={16}>
      <KpiGrid cols={4}>
        <KpiTile
          label="Saved outlook"
          value={
            outlook ? (
              <DirectionBadge direction={safeDirection(outlook.direction)} />
            ) : (
              "Unavailable"
            )
          }
          hint={
            outlook ? `${outlook.strength_label} · target ${formatDate(outlook.date)}` : undefined
          }
          info="Saved experimental direction and score. Strength is not a probability."
        />
        {quoteCards.map((quote) => (
          <KpiTile
            key={quote.key}
            label={quote.name}
            value={quote.value}
            delta={quote.delta}
            hint={quote.hint}
          />
        ))}
      </KpiGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing={12}>
        <Panel title="Outlook evidence">
          {outlook ? (
            <Stack gap={10}>
              <Group justify="space-between">
                <Text fw={600}>
                  {outlook.direction === "withheld"
                    ? "No direction"
                    : `Likely ${outlook.direction}`}
                </Text>
                <StrengthMeter score={Number(outlook.strength)} />
              </Group>
              <Text size="sm" c="dimmed">
                News score {outlook.news_score} from {outlook.news_articles} articles · Global cue
                score {outlook.global_score}
              </Text>
              <DataTable
                columns={[
                  { label: "Cue", render: (cue) => cue.name },
                  { label: "Change", render: (cue) => cue.change },
                  { label: "Saved for", render: (cue) => formatDate(cue.as_of) },
                ]}
                rows={outlook.cues}
                rowKey={(cue) => `${cue.name}-${cue.as_of}`}
                empty="No outlook evidence is available."
              />
              {outlook.notes.map((note) => (
                <Text key={note} size="xs" c="dimmed">
                  {note}
                </Text>
              ))}
            </Stack>
          ) : (
            <EmptyState
              title="No saved outlook available"
              description="Markets or news data may be unavailable."
            />
          )}
        </Panel>
        <Panel title="Company watchlist">
          {data.stocks_watch?.items.length ? (
            <DataTable
              columns={[
                {
                  label: "Company",
                  render: (item) => {
                    const quote = live.companies.get(item.id);
                    return (
                      <Stack gap={1}>
                        <Anchor component={AppLink} href={`/v2/companies/${item.id}/`}>
                          {item.name} ({item.symbol})
                        </Anchor>
                        <Text size="xs" c="dimmed">
                          {quote
                            ? `Live · ${formatInr(quote.ltp)}`
                            : `Live price ${live.connection}`}
                        </Text>
                      </Stack>
                    );
                  },
                },
                {
                  label: "News bias",
                  render: (item) => <Badge variant="light">{item.bias}</Badge>,
                },
                { label: "Articles", render: (item) => item.articles },
                { label: "Score", render: (item) => formatNumber(item.score, 2) },
              ]}
              rows={data.stocks_watch.items}
              rowKey={(item) => item.id}
              empty="No companies match the current watchlist."
            />
          ) : (
            <EmptyState
              title="Watchlist unavailable"
              description="This section requires enabled Companies, Markets, and News data."
            />
          )}
        </Panel>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 3 }} spacing={12}>
        <Panel title="Market breadth">
          {market ? (
            <Stack gap={8}>
              <Text size="sm">Coverage: {market.movers.coverage} saved quotes</Text>
              <Group gap={16}>
                <Text c="var(--kv2-gain)">Advancing {market.movers.advancing}</Text>
                <Text c="var(--kv2-loss)">Declining {market.movers.declining}</Text>
                <Text c="dimmed">Unchanged {market.movers.unchanged}</Text>
              </Group>
              <Text size="xs" c="dimmed">
                As of {market.movers.as_of ? formatTimestamp(market.movers.as_of) : "not available"}
              </Text>
            </Stack>
          ) : (
            <EmptyState title="Market breadth unavailable" />
          )}
        </Panel>
        <Panel title="News highlights">
          {data.news ? (
            <Stack gap={8}>
              <Text size="sm">
                {data.news.articles} articles · {data.news.positive} positive · {data.news.negative}{" "}
                negative
              </Text>
              {[...data.news.good, ...data.news.bad].slice(0, 5).map((story) => (
                <Anchor
                  key={`${story.url}-${story.title}`}
                  href={story.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {story.title}{" "}
                  <Text span size="xs" c="dimmed">
                    · {story.source} · score {story.score}
                  </Text>
                </Anchor>
              ))}
            </Stack>
          ) : (
            <EmptyState title="News unavailable" />
          )}
        </Panel>
        <Panel title="Latest report">
          {data.report ? (
            <Stack gap={8}>
              <Text fw={600}>{formatDate(data.report.date)}</Text>
              <Group>
                <DirectionBadge direction={safeDirection(data.report.prediction)} />
                <Text size="sm">
                  {data.report.strength ? `Strength ${data.report.strength}` : "No score"}
                </Text>
              </Group>
              <Anchor component={AppLink} href={`/v2/reports/${data.report.date}/`}>
                Open report
              </Anchor>
            </Stack>
          ) : (
            <EmptyState title="No report available" />
          )}
        </Panel>
      </SimpleGrid>

      {data.ipos ? (
        <Panel title="IPO watch">
          <DataTable
            columns={[
              { label: "Issue", render: (ipo) => ipo.name },
              { label: "Category", render: (ipo) => ipo.category },
              { label: "Status", render: (ipo) => ipo.status },
              {
                label: "Dates",
                render: (ipo) => `${ipo.open_date ?? "—"} – ${ipo.close_date ?? "—"}`,
              },
              { label: "Price band", render: (ipo) => ipo.price_band },
              { label: "Verdict", render: (ipo) => ipo.verdict },
            ]}
            rows={[...data.ipos.open_now, ...data.ipos.upcoming, ...data.ipos.likely_good]}
            rowKey={(ipo) => `${ipo.name}-${ipo.open_date ?? ipo.status}`}
            empty="No IPOs in the configured watch window."
          />
        </Panel>
      ) : null}
    </Stack>
  );
}

export function CompaniesPage() {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [index, setIndex] = useState("NIFTY_50");
  const [page, setPage] = useState(1);
  const [refreshTask, setRefreshTask] = useState("");
  const { data: session } = useSuspenseQuery(sessionQuery);
  const queryClient = useQueryClient();
  const query = useQuery(
    companiesQuery({ q, page, page_size: pageSize, sector: sector ?? undefined, index }),
  );
  const refresh = useMutation({
    mutationFn: refreshCompanyList,
    onSuccess: ({ task_id }) => {
      setRefreshTask(task_id);
      notifications.show({
        title: "Company catalog refresh started",
        message: "The server is processing the request.",
      });
    },
    onError: (error) =>
      notifications.show({ title: "Refresh failed", message: String(error), color: "red" }),
  });
  const status = useQuery({
    ...companyListRefreshStatusQuery(refreshTask),
    enabled: Boolean(refreshTask),
    refetchInterval: (q) =>
      ["success", "failure"].includes(q.state.data?.status ?? "") ? false : 1500,
  });
  useEffect(() => {
    if (status.data?.status === "success") {
      void queryClient.invalidateQueries({ queryKey: ["app", "companies"] });
    }
  }, [queryClient, status.data?.status]);
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Companies"
        description="Search the saved company directory and view available fundamentals, market observations, news and linked IPOs."
        actions={
          session.is_staff ? (
            <Button
              variant="default"
              leftSection={<LuRefreshCw size={14} />}
              loading={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              Refresh catalog
            </Button>
          ) : undefined
        }
        meta={data ? <Badge variant="light">{data.total} companies</Badge> : undefined}
      />
      <Stack gap={12}>
        <Group align="end" grow>
          <TextInput
            label="Search"
            placeholder="Name, symbol or sector"
            value={q}
            onChange={(e) => {
              setQ(e.currentTarget.value);
              setPage(1);
            }}
          />
          <Select
            label="Index"
            value={index}
            onChange={(value) => {
              setIndex(value ?? "");
              setPage(1);
            }}
            data={[
              { value: "", label: "All indices" },
              ...(data?.indices ?? []).map((item) => ({
                value: item.value,
                label: `${item.label} (${item.count})`,
              })),
            ]}
          />
          <Select
            label="Sector"
            clearable
            value={sector}
            onChange={(value) => {
              setSector(value);
              setPage(1);
            }}
            data={(data?.sectors ?? []).map((value) => ({ value, label: value }))}
          />
        </Group>
        {refreshTask && status.data ? (
          <Text size="xs" c="dimmed">
            Catalog refresh: {status.data.status}
          </Text>
        ) : null}
        <Panel title="Company directory" flush>
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <>
                <DataTable
                  columns={[
                    {
                      label: "Company",
                      render: (c: CompanyItem) => (
                        <Stack gap={2}>
                          <Anchor component={AppLink} href={`/v2/companies/${c.id}/`}>
                            {c.name}
                          </Anchor>
                          <Text size="xs" c="dimmed">
                            {c.symbol} · {c.listings.map((item) => item.exchange).join(", ")}
                          </Text>
                        </Stack>
                      ),
                    },
                    { label: "Sector", render: (c: CompanyItem) => c.sector || "—" },
                    {
                      label: "Last updated",
                      render: (c: CompanyItem) =>
                        c.last_updated ? formatTimestamp(c.last_updated) : "—",
                    },
                  ]}
                  rows={data.items}
                  rowKey={(c) => c.id}
                  empty="No companies match these filters."
                />
                <PageNumber page={data.page} pages={data.pages} onChange={setPage} />
              </>
            ) : null}
          </QueryState>
        </Panel>
      </Stack>
    </Page>
  );
}

export function CompanyDetailPage({ id }: { id: string }) {
  const numericId = Number(id);
  const query = useQuery(companyQuery(numericId > 0 ? String(numericId) : id));
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title={data?.company.name ?? "Company"}
        crumbs={[
          { label: "Companies", to: "/v2/companies/" },
          { label: data?.company.symbol ?? id },
        ]}
        description={data?.summary}
        meta={
          data ? (
            <Badge variant="light">{data.company.sector || "Sector unavailable"}</Badge>
          ) : undefined
        }
      />
      <QueryState pending={query.isPending} error={query.error} retry={() => void query.refetch()}>
        {data ? <CompanyDetailContent data={data} /> : null}
      </QueryState>
    </Page>
  );
}

function CompanyDetailContent({ data }: { data: CompanyDetail }) {
  const {
    company,
    quote,
    fundamentals,
    candles,
    outlook,
    outlook_history: history,
    news,
    ipos,
  } = data;
  const canStream = data.markets_available && Boolean(data.instrument_key);
  const live = useLiveQuotes(canStream ? [company.id] : [], canStream);
  const liveQuote = live.companies.get(company.id);
  const changePct = liveQuote?.change_pct ?? quote?.change_pct ?? null;
  const volume = liveQuote?.volume ?? quote?.volume ?? null;
  const candleRows = candles.slice(-30).reverse();
  const chartCandles = candles.map(({ day, ...bar }) => ({ date: day, ...bar }));
  return (
    <Stack gap={14}>
      <KpiGrid cols={4}>
        <KpiTile
          label={liveQuote ? "Live price" : "Latest saved price"}
          value={
            liveQuote ? formatInr(liveQuote.ltp) : quote ? formatInr(quote.price) : "Unavailable"
          }
          hint={
            liveQuote
              ? `${live.connection} · ${formatTimestamp(liveQuote.as_of)}`
              : quote
                ? `${quote.mode} · ${formatTimestamp(quote.as_of)}`
                : "No saved quote"
          }
        />
        <KpiTile label="1D change" value={changePct === null ? "—" : <Delta value={changePct} />} />
        <KpiTile label="Volume" value={volume === null ? "—" : formatNumber(volume)} />
        <KpiTile
          label="Latest outlook"
          value={
            outlook ? (
              <DirectionBadge direction={safeDirection(outlook.direction)} />
            ) : (
              "Unavailable"
            )
          }
          hint={
            outlook
              ? `${formatDate(outlook.target_date)} · ${formatNumber(outlook.score, 2)}`
              : undefined
          }
        />
      </KpiGrid>
      {data.errors &&
        Object.entries(data.errors).map(([key, value]) => (
          <Text key={key} size="xs" c="dimmed">
            {key}: {value}
          </Text>
        ))}
      <Tabs defaultValue="overview">
        <Tabs.List>
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="fundamentals">Fundamentals</Tabs.Tab>
          <Tabs.Tab value="signals">Signals</Tabs.Tab>
          <Tabs.Tab value="news">News ({news.length})</Tabs.Tab>
          <Tabs.Tab value="ipos">IPO history ({ipos.length})</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="overview" pt="md">
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Stack gap={12}>
              <Panel title="Saved daily bars">
                <CandlestickChart candles={chartCandles} overlays={["sma20", "sma50"]} />
                <DataTable
                  columns={[
                    { label: "Date", render: (bar) => formatDate(bar.day) },
                    { label: "Open", render: (bar) => formatInr(bar.open) },
                    {
                      label: "High / low",
                      render: (bar) => `${formatInr(bar.high)} / ${formatInr(bar.low)}`,
                    },
                    { label: "Close", render: (bar) => formatInr(bar.close) },
                    { label: "Volume", render: (bar) => formatNumber(bar.volume) },
                  ]}
                  rows={candleRows}
                  rowKey={(bar) => bar.day}
                  empty="No saved daily bars are available."
                />
              </Panel>
              <Panel title="Live quote & market depth">
                {liveQuote ? (
                  <DataTable
                    columns={[
                      { label: "Bid qty", render: (level) => formatNumber(level.bid_qty) },
                      {
                        label: "Bid price",
                        render: (level) =>
                          level.bid_price === null ? "—" : formatInr(level.bid_price),
                      },
                      {
                        label: "Ask price",
                        render: (level) =>
                          level.ask_price === null ? "—" : formatInr(level.ask_price),
                      },
                      { label: "Ask qty", render: (level) => formatNumber(level.ask_qty) },
                    ]}
                    rows={liveQuote.depth}
                    rowKey={(level) =>
                      `${level.bid_price}-${level.bid_qty}-${level.ask_price}-${level.ask_qty}`
                    }
                    empty="No live market depth is available."
                  />
                ) : (
                  <Text size="sm" c="dimmed">
                    {canStream
                      ? `Waiting for the live quote stream (${live.connection}).`
                      : "Live quotes are not enabled for this company."}
                  </Text>
                )}
              </Panel>
            </Stack>
            <Panel title="Company facts">
              <Stack gap={6}>
                <Text size="xs" c="dimmed">
                  Source: {data.fundamentals_source || "Not recorded"}
                  {data.fundamentals_as_of ? ` · ${formatTimestamp(data.fundamentals_as_of)}` : ""}
                </Text>
                <DataTable
                  columns={[
                    { label: "Metric", render: ([key]) => key },
                    {
                      label: "Value",
                      render: ([, value]) =>
                        typeof value === "object" ? JSON.stringify(value) : String(value ?? "—"),
                    },
                  ]}
                  rows={Object.entries(fundamentals)}
                  rowKey={([key]) => key}
                  empty="No fundamentals are available."
                />
              </Stack>
            </Panel>
          </SimpleGrid>
        </Tabs.Panel>
        <Tabs.Panel value="fundamentals" pt="md">
          <Panel
            title="Available fundamentals"
            info="Only facts returned by the saved company fundamentals endpoint are shown."
          >
            <DataTable
              columns={[
                { label: "Metric", render: ([key]) => key },
                {
                  label: "Value",
                  render: ([, value]) =>
                    typeof value === "object" ? JSON.stringify(value) : String(value ?? "—"),
                },
              ]}
              rows={Object.entries(fundamentals)}
              rowKey={([key]) => key}
              empty="No fundamentals are available."
            />
          </Panel>
        </Tabs.Panel>
        <Tabs.Panel value="signals" pt="md">
          <Stack gap={12}>
            <Panel title="Latest saved signal">
              {outlook ? (
                <Stack>
                  <Group>
                    <DirectionBadge direction={safeDirection(outlook.direction)} />
                    <Text size="sm">
                      Score {formatNumber(outlook.score, 2)} · momentum{" "}
                      {formatNumber(outlook.momentum_score, 2)}
                    </Text>
                  </Group>
                  <Text size="xs" c="dimmed">
                    Target {formatDate(outlook.target_date)} · saved{" "}
                    {formatTimestamp(outlook.created_at)}
                  </Text>
                  <Text size="sm">{JSON.stringify(outlook.inputs)}</Text>
                </Stack>
              ) : (
                <EmptyState title="No saved company outlook" />
              )}
            </Panel>
            <Panel title="Outlook history">
              <DataTable
                columns={[
                  { label: "Target date", render: (signal) => formatDate(signal.target_date) },
                  {
                    label: "Direction",
                    render: (signal) => (
                      <DirectionBadge direction={safeDirection(signal.direction)} />
                    ),
                  },
                  { label: "Score", render: (signal) => formatNumber(signal.score, 2) },
                  { label: "Momentum", render: (signal) => formatNumber(signal.momentum_score, 2) },
                  {
                    label: "News",
                    render: (signal) =>
                      signal.news_score === null ? "—" : formatNumber(signal.news_score, 2),
                  },
                ]}
                rows={history ?? []}
                rowKey={(signal) => `${signal.target_date}-${signal.created_at}`}
                empty="No saved signal history."
              />
            </Panel>
          </Stack>
        </Tabs.Panel>
        <Tabs.Panel value="news" pt="md">
          <Panel title="Scored company news">
            <CompanyNewsTable rows={news} />
          </Panel>
        </Tabs.Panel>
        <Tabs.Panel value="ipos" pt="md">
          <Panel title="Linked IPOs">
            <DataTable
              columns={[
                {
                  label: "Issue",
                  render: (ipo) => (
                    <Anchor component={AppLink} href={`/v2/ipos/${ipo.id}/`}>
                      {ipo.name}
                    </Anchor>
                  ),
                },
                { label: "Verdict", render: (ipo) => ipo.verdict },
                {
                  label: "Score",
                  render: (ipo) => (ipo.score === null ? "—" : formatNumber(ipo.score, 1)),
                },
                {
                  label: "Scored at",
                  render: (ipo) => (ipo.scored_at ? formatTimestamp(ipo.scored_at) : "—"),
                },
                { label: "Evidence", render: (ipo) => JSON.stringify(ipo.score_inputs) },
              ]}
              rows={ipos}
              rowKey={(ipo) => ipo.id}
              empty="No linked IPO scores are available."
            />
          </Panel>
        </Tabs.Panel>
      </Tabs>
      <Text size="xs" c="dimmed">
        Symbol {company.symbol} ·{" "}
        {company.listings.map((listing) => `${listing.exchange}: ${listing.symbol}`).join(" · ") ||
          "No exchange listings"}
      </Text>
    </Stack>
  );
}

function CompanyNewsTable({ rows }: { rows: CompanyDetail["news"] }) {
  return (
    <DataTable
      columns={[
        {
          label: "Story",
          render: (story) => (
            <Stack gap={2}>
              <Anchor href={story.url} target="_blank" rel="noreferrer">
                {story.title} <LuExternalLink size={12} />
              </Anchor>
              <Text size="xs" c="dimmed">
                {story.source} ·{" "}
                {story.published_at ? formatTimestamp(story.published_at) : "date unavailable"}
              </Text>
              <Text size="xs" c="dimmed">
                {story.sentiment_reason}
              </Text>
            </Stack>
          ),
        },
        {
          label: "Sentiment",
          render: (story) =>
            story.sentiment_score === null ? "Unscored" : formatNumber(story.sentiment_score, 2),
        },
        {
          label: "Relevance",
          render: (story) => (story.relevance === null ? "—" : formatNumber(story.relevance, 2)),
        },
        { label: "Reason", render: (story) => story.sentiment_reason || "—" },
      ]}
      rows={rows}
      rowKey={(story) => `${story.url}-${story.title}`}
      empty="No linked news stories."
    />
  );
}

export function MarketsPage({ initialTab = "track" }: { initialTab?: string }) {
  const [companySearch, setCompanySearch] = useState("");
  const [companyPage, setCompanyPage] = useState(1);
  const query = useQuery(marketsQuery());
  const calendar = useQuery(calendarQuery(new Date().getFullYear()));
  const companies = useQuery(
    companyMarketsQuery({ q: companySearch, page: companyPage, page_size: pageSize }),
  );
  const live = useLiveQuotes(companies.data?.items.map((item) => item.id) ?? []);
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Markets"
        description="Saved outlook history, measured track record, configured market status and exchange instruments."
        meta={
          calendar.data ? (
            <StatusBadge tone={calendar.data.is_open ? "gain" : "neutral"}>
              {calendar.data.status_key}
            </StatusBadge>
          ) : undefined
        }
      />
      <Tabs value={initialTab} onChange={() => {}}>
        <Tabs.List>
          <Tabs.Tab value="track">Track record</Tabs.Tab>
          <Tabs.Tab value="live">Live quotes</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="track" pt="md">
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <Stack gap={12}>
                <KpiGrid cols={4}>
                  <KpiTile
                    label="Evaluated"
                    value={data.stats.total}
                    hint={`${data.stats.correct} correct`}
                  />
                  <KpiTile
                    label="Accuracy"
                    value={data.stats.accuracy}
                    hint={`Baseline ${data.stats.baseline_accuracy}`}
                  />
                  <KpiTile
                    label="High confidence"
                    value={`${data.stats.high_confidence.correct}/${data.stats.high_confidence.n}`}
                    hint="Saved high-strength results"
                  />
                  <KpiTile
                    label="Pending"
                    value={data.stats.pending}
                    hint={data.stats.enough_results ? "30+ results available" : "Limited history"}
                  />
                </KpiGrid>
                <Panel title="Latest saved quotes">
                  <DataTable
                    columns={[
                      { label: "Instrument", render: (quote) => quote.name },
                      { label: "Close", render: (quote) => quote.close },
                      { label: "Change", render: (quote) => quote.change },
                      { label: "Date", render: (quote) => formatDate(quote.day) },
                    ]}
                    rows={data.quotes}
                    rowKey={(quote) => `${quote.name}-${quote.day}`}
                    empty="No saved market quotes."
                  />
                </Panel>
                <Panel
                  title="Company market observations"
                  info="Prices are persisted observations from the configured market feed; missing quotes are shown explicitly."
                >
                  <QueryState
                    pending={companies.isPending}
                    error={companies.error}
                    retry={() => void companies.refetch()}
                  >
                    {companies.data ? (
                      <DataTable
                        columns={[
                          {
                            label: "Company",
                            render: (item) => (
                              <Anchor component={AppLink} href={`/v2/companies/${item.id}/`}>
                                {item.name} ({item.symbol})
                              </Anchor>
                            ),
                          },
                          {
                            label: "Saved price",
                            render: (item) =>
                              item.quote ? formatInr(item.quote.price) : "Unavailable",
                          },
                          {
                            label: "Change",
                            render: (item) =>
                              item.quote?.change_pct == null
                                ? "—"
                                : `${item.quote.change_pct > 0 ? "+" : ""}${formatNumber(item.quote.change_pct, 2)}%`,
                          },
                          {
                            label: "Volume",
                            render: (item) =>
                              item.quote?.volume == null ? "—" : formatNumber(item.quote.volume),
                          },
                          {
                            label: "As of",
                            render: (item) =>
                              item.quote
                                ? formatTimestamp(item.quote.as_of)
                                : item.error || "No quote",
                          },
                        ]}
                        rows={companies.data.items}
                        rowKey={(item) => item.id}
                        empty="No saved company observations."
                      />
                    ) : null}
                  </QueryState>
                </Panel>
                <Panel title="Prediction history">
                  <DataTable
                    columns={[
                      { label: "Target date", render: (item) => formatDate(item.date) },
                      {
                        label: "Direction",
                        render: (item) => (
                          <DirectionBadge direction={safeDirection(item.direction)} />
                        ),
                      },
                      { label: "Strength", render: (item) => item.strength },
                      { label: "Actual", render: (item) => item.actual_direction || "Waiting" },
                      { label: "Change", render: (item) => item.change },
                      {
                        label: "Result",
                        render: (item) => <Badge variant="light">{item.result}</Badge>,
                      },
                    ]}
                    rows={data.history}
                    rowKey={(item) => item.date}
                    empty="No prediction history is available."
                  />
                </Panel>
              </Stack>
            ) : null}
          </QueryState>
        </Tabs.Panel>
        <Tabs.Panel value="live" pt="md">
          <Stack gap={12}>
            <Panel title="Market status">
              <Group justify="space-between">
                <Text size="sm">
                  {live.status?.as_of
                    ? `Status updated ${formatTimestamp(live.status.as_of)}`
                    : "Waiting for saved live status"}
                </Text>
                <Badge variant="light">{live.connection}</Badge>
              </Group>
              {live.status ? (
                <DataTable
                  columns={[
                    { label: "Segment", render: ([segment]) => segment },
                    { label: "Status", render: ([, state]) => state },
                  ]}
                  rows={Object.entries(live.status.segments)}
                  rowKey={([segment]) => segment}
                  empty="No market segments."
                />
              ) : null}
              <DataTable
                columns={[
                  { label: "Live instrument", render: (quote) => quote.name || quote.symbol },
                  { label: "Last traded price", render: (quote) => formatInr(quote.ltp) },
                  {
                    label: "Change",
                    render: (quote) =>
                      quote.change_pct == null
                        ? "—"
                        : `${quote.change_pct > 0 ? "+" : ""}${formatNumber(quote.change_pct, 2)}%`,
                  },
                  { label: "As of", render: (quote) => formatTimestamp(quote.as_of) },
                ]}
                rows={live.indices}
                rowKey={(quote) => quote.key}
                empty="No live index quotes are streaming."
              />
            </Panel>
            <Panel title="Company quotes">
              <TextInput
                label="Search company"
                placeholder="Company name or symbol"
                value={companySearch}
                onChange={(event) => {
                  setCompanySearch(event.currentTarget.value);
                  setCompanyPage(1);
                }}
                mb="sm"
              />
              <QueryState
                pending={companies.isPending}
                error={companies.error}
                retry={() => void companies.refetch()}
              >
                {companies.data ? (
                  <>
                    <DataTable
                      columns={[
                        {
                          label: "Company",
                          render: (item) => (
                            <Anchor component={AppLink} href={`/v2/companies/${item.id}/`}>
                              {item.name} ({item.symbol})
                            </Anchor>
                          ),
                        },
                        {
                          label: "Last price",
                          render: (item) => {
                            const quote = live.companies.get(item.id);
                            return quote
                              ? formatInr(quote.ltp)
                              : item.quote
                                ? formatInr(item.quote.price)
                                : "Unavailable";
                          },
                        },
                        {
                          label: "Change",
                          render: (item) => {
                            const change = live.companies.get(item.id)?.change_pct;
                            const savedChange = item.quote?.change_pct;
                            const value = change ?? savedChange;
                            return value == null
                              ? "—"
                              : `${value > 0 ? "+" : ""}${formatNumber(value, 2)}%`;
                          },
                        },
                        {
                          label: "Volume",
                          render: (item) => {
                            const volume =
                              live.companies.get(item.id)?.volume ?? item.quote?.volume;
                            return volume == null ? "—" : formatNumber(volume);
                          },
                        },
                        {
                          label: "Freshness",
                          render: (item) => {
                            const quote = live.companies.get(item.id);
                            if (quote) return `Live · ${formatTimestamp(quote.as_of)}`;
                            return item.quote
                              ? `Saved ${item.quote.mode} · ${formatTimestamp(item.quote.as_of)}`
                              : item.error || "No quote";
                          },
                        },
                      ]}
                      rows={companies.data.items}
                      rowKey={(item) => item.id}
                      empty="No company quotes match this search."
                    />
                    <PageNumber
                      page={companies.data.page}
                      pages={companies.data.pages}
                      onChange={setCompanyPage}
                    />
                  </>
                ) : null}
              </QueryState>
            </Panel>
            <Panel title={`Trading calendar ${calendar.data?.year ?? ""}`}>
              <QueryState
                pending={calendar.isPending}
                error={calendar.error}
                retry={() => void calendar.refetch()}
              >
                {calendar.data ? (
                  <>
                    <Text size="sm">
                      {calendar.data.reason}
                      {calendar.data.special_reason ? ` · ${calendar.data.special_reason}` : ""}
                    </Text>
                    <DataTable
                      columns={[
                        { label: "Date", render: (day) => formatDate(day.day) },
                        { label: "Status", render: (day) => day.kind },
                        { label: "Reason", render: (day) => day.reason },
                      ]}
                      rows={calendar.data.days}
                      rowKey={(day) => day.day}
                      empty="No calendar exceptions for this year."
                    />
                  </>
                ) : null}
              </QueryState>
            </Panel>
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Page>
  );
}

export function MarketInstrumentsPage() {
  const [q, setQ] = useState("");
  const [exchange, setExchange] = useState<string | null>(null);
  const [segment, setSegment] = useState<string | null>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const query = useQuery(
    exchangeInstrumentsQuery({
      q,
      page,
      page_size: pageSize,
      exchange: (exchange ?? "") as "" | "NSE" | "BSE",
      segment: segment ?? "",
      instrument_type: kind ?? "",
    }),
  );
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Exchange instruments"
        crumbs={[{ label: "Markets", to: "/v2/markets/" }]}
        description="Search the persisted exchange instrument master."
      />
      <Stack gap={12}>
        <Group grow align="end">
          <TextInput
            label="Search instruments"
            value={q}
            onChange={(event) => {
              setQ(event.currentTarget.value);
              setPage(1);
            }}
          />
          <Select
            label="Exchange"
            clearable
            value={exchange}
            onChange={(value) => {
              setExchange(value);
              setPage(1);
            }}
            data={["NSE", "BSE"]}
          />
          <Select
            label="Segment"
            clearable
            value={segment}
            onChange={(value) => {
              setSegment(value);
              setPage(1);
            }}
            data={(data?.segments ?? []).map((value) => ({ value, label: value }))}
          />
          <Select
            label="Instrument type"
            clearable
            value={kind}
            onChange={(value) => {
              setKind(value);
              setPage(1);
            }}
            data={(data?.instrument_types ?? []).map((value) => ({ value, label: value }))}
          />
        </Group>
        <Panel title="Instrument master">
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <>
                <DataTable
                  columns={[
                    { label: "Symbol", render: (item) => item.trading_symbol },
                    { label: "Name", render: (item) => item.name },
                    { label: "Exchange", render: (item) => item.exchange },
                    { label: "Segment", render: (item) => item.segment },
                    { label: "Type", render: (item) => item.instrument_type },
                    {
                      label: "Expiry",
                      render: (item) => (item.expiry ? formatDate(item.expiry) : "—"),
                    },
                  ]}
                  rows={data.items}
                  rowKey={(item) => item.instrument_key}
                  empty="No instruments match these filters."
                />
                <PageNumber page={data.page} pages={data.pages} onChange={setPage} />
              </>
            ) : null}
          </QueryState>
        </Panel>
      </Stack>
    </Page>
  );
}

export function NewsPage() {
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [coverage, setCoverage] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery(
    newsQuery({
      q,
      source,
      coverage: coverage as "" | "india" | "international",
      sentiment: sentiment as "" | "positive" | "negative" | "neutral" | "unscored",
      page,
      page_size: pageSize,
    }),
  );
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="News"
        description="Search and filter the saved news feed and its available sentiment analysis."
        meta={data ? <Badge variant="light">{data.total} stories</Badge> : undefined}
      />
      <Stack gap={12}>
        <Group grow align="end">
          <TextInput
            label="Search headlines and summaries"
            value={q}
            onChange={(event) => {
              setQ(event.currentTarget.value);
              setPage(1);
            }}
          />
          <Select
            label="Source"
            clearable
            value={source || null}
            onChange={(value) => {
              setSource(value ?? "");
              setPage(1);
            }}
            data={(data?.sources ?? []).map((value) => ({ value, label: value }))}
          />
          <Select
            label="Coverage"
            clearable
            value={coverage || null}
            onChange={(value) => {
              setCoverage(value ?? "");
              setPage(1);
            }}
            data={[
              { value: "india", label: "India" },
              { value: "international", label: "International" },
            ]}
          />
          <Select
            label="Sentiment"
            clearable
            value={sentiment || null}
            onChange={(value) => {
              setSentiment(value ?? "");
              setPage(1);
            }}
            data={(data?.sentiments ?? []).map((item) => ({
              value: item.value,
              label: item.label,
            }))}
          />
        </Group>
        <Panel title="News feed">
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <>
                <DataTable
                  columns={[
                    {
                      label: "Story",
                      render: (item: NewsItem) => (
                        <Stack gap={2}>
                          <Anchor href={item.url} target="_blank" rel="noreferrer">
                            {item.title} <LuExternalLink size={12} />
                          </Anchor>
                          <Text size="xs" c="dimmed">
                            {item.source} ·{" "}
                            {item.published_at
                              ? formatTimestamp(item.published_at)
                              : "Date unavailable"}
                          </Text>
                        </Stack>
                      ),
                    },
                    {
                      label: "Sentiment",
                      render: (item: NewsItem) =>
                        `${item.sentiment}${item.score ? ` · ${item.score}` : ""}`,
                    },
                    { label: "Relevance", render: (item: NewsItem) => item.relevance ?? "—" },
                    { label: "Coverage", render: (item: NewsItem) => item.coverage || "—" },
                  ]}
                  rows={data.items}
                  rowKey={(item) => item.id}
                  empty="No news stories match these filters."
                />
                <PageNumber page={data.page} pages={data.pages} onChange={setPage} />
              </>
            ) : null}
          </QueryState>
        </Panel>
      </Stack>
    </Page>
  );
}

export function IposPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [verdict, setVerdict] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery(
    iposQuery({
      q,
      status: status as "" | "open" | "upcoming" | "closed" | "listed" | "all",
      verdict: verdict as "" | "good" | "mixed" | "weak" | "unknown",
      category: category as "" | "mainboard" | "sme",
      page,
      page_size: pageSize,
    }),
  );
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="IPOs"
        description="Existing issue facts, saved scoring evidence and reported subscription data. Grey-market figures are unofficial."
        meta={data ? <Badge variant="light">{data.total} issues</Badge> : undefined}
      />
      <Stack gap={12}>
        <Group grow align="end">
          <TextInput
            label="Search issues"
            value={q}
            onChange={(event) => {
              setQ(event.currentTarget.value);
              setPage(1);
            }}
          />
          <Select
            label="Status"
            clearable
            value={status || null}
            onChange={(value) => {
              setStatus(value ?? "");
              setPage(1);
            }}
            data={(data?.statuses ?? []).map((item) => ({ value: item.value, label: item.label }))}
          />
          <Select
            label="Verdict"
            clearable
            value={verdict || null}
            onChange={(value) => {
              setVerdict(value ?? "");
              setPage(1);
            }}
            data={(data?.verdicts ?? []).map((item) => ({ value: item.value, label: item.label }))}
          />
          <Select
            label="Category"
            clearable
            value={category || null}
            onChange={(value) => {
              setCategory(value ?? "");
              setPage(1);
            }}
            data={(data?.categories ?? []).map((item) => ({
              value: item.value,
              label: item.label,
            }))}
          />
        </Group>
        <Panel title="Issue list">
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <>
                <IpoTable rows={data.items} />
                <PageNumber page={data.page} pages={data.pages} onChange={setPage} />
              </>
            ) : null}
          </QueryState>
        </Panel>
      </Stack>
    </Page>
  );
}

function IpoTable({ rows }: { rows: IpoSummary[] }) {
  return (
    <DataTable
      columns={[
        {
          label: "Issue",
          render: (ipo) => (
            <Anchor component={AppLink} href={`/v2/ipos/${ipo.id}/`}>
              {ipo.name}
            </Anchor>
          ),
        },
        { label: "Category", render: (ipo) => ipo.category },
        { label: "Status", render: (ipo) => ipo.status },
        { label: "Dates", render: (ipo) => ipo.dates },
        { label: "Price band", render: (ipo) => ipo.price_band },
        { label: "GMP", render: (ipo) => ipo.gmp },
        { label: "Subscription", render: (ipo) => ipo.subscribed },
        { label: "Listing gain", render: (ipo) => ipo.listing_gain },
        { label: "Score / verdict", render: (ipo) => `${ipo.score ?? "—"} · ${ipo.verdict}` },
      ]}
      rows={rows}
      rowKey={(ipo) => ipo.id}
      empty="No IPOs match these filters."
    />
  );
}

export function IpoDetailPage({ id }: { id: string }) {
  const query = useQuery(ipoQuery(id));
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title={data?.name ?? "IPO detail"}
        crumbs={[{ label: "IPOs", to: "/v2/ipos/" }, { label: data?.name ?? id }]}
        description={data?.notes.join(" · ")}
        meta={data ? <Badge variant="light">{data.verdict}</Badge> : undefined}
      />
      <QueryState pending={query.isPending} error={query.error} retry={() => void query.refetch()}>
        {data ? <IpoDetailContent data={data} /> : null}
      </QueryState>
    </Page>
  );
}

function IpoDetailContent({ data }: { data: IpoDetail }) {
  return (
    <Stack gap={12}>
      <KpiGrid cols={4}>
        <KpiTile label="Category" value={data.category} />
        <KpiTile label="Status" value={data.status} />
        <KpiTile label="Price band" value={data.price_band} />
        <KpiTile label="Verdict" value={data.verdict} />
      </KpiGrid>
      <KpiGrid cols={4}>
        <KpiTile label="GMP" value={data.gmp} hint="Unofficial indicator, not a guarantee." />
        <KpiTile label="Subscription" value={data.subscribed} />
        <KpiTile label="Listing gain" value={data.listing_gain} />
        <KpiTile
          label="Score"
          value={data.score ?? "Unavailable"}
          hint={data.scored_at ? `Scored ${formatTimestamp(data.scored_at)}` : undefined}
        />
      </KpiGrid>
      <Panel title="Issue facts">
        <DataTable
          columns={[
            { label: "Fact", render: (fact) => fact.label },
            { label: "Value", render: (fact) => fact.value },
          ]}
          rows={data.facts}
          rowKey={(fact) => `${fact.label}-${fact.value}`}
          empty="No issue facts are available."
        />
      </Panel>
      <Panel title="Scoring signals">
        <DataTable
          columns={[
            { label: "Signal", render: (signal) => signal.name },
            { label: "Value", render: (signal) => signal.value },
            { label: "Normalized score", render: (signal) => signal.signal },
          ]}
          rows={data.signals}
          rowKey={(signal) => signal.name}
          empty="No scoring inputs are available."
        />
      </Panel>
      {data.notes.map((note) => (
        <Text key={note} size="sm" c="dimmed">
          {note}
        </Text>
      ))}
    </Stack>
  );
}

export function ReportsPage() {
  const [q, setQ] = useState("");
  const [direction, setDirection] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery(
    reportsQuery({
      page,
      page_size: pageSize,
      q,
      direction: direction as "" | "up" | "down" | "flat" | "unknown",
    }),
  );
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Reports"
        description="Browse saved daily reports and their recorded outlook."
        meta={data ? <Badge variant="light">{data.total} reports</Badge> : undefined}
      />
      <Stack gap={12}>
        <Group grow>
          <TextInput
            label="Search dates"
            value={q}
            onChange={(event) => {
              setQ(event.currentTarget.value);
              setPage(1);
            }}
          />
          <Select
            label="Direction"
            clearable
            value={direction || null}
            onChange={(value) => {
              setDirection(value ?? "");
              setPage(1);
            }}
            data={[
              { value: "up", label: "Up" },
              { value: "down", label: "Down" },
              { value: "flat", label: "Flat" },
              { value: "unknown", label: "Unknown" },
            ]}
          />
        </Group>
        <Panel title="Report archive">
          <QueryState
            pending={query.isPending}
            error={query.error}
            retry={() => void query.refetch()}
          >
            {data ? (
              <>
                <ReportTable rows={data.items} />
                <PageNumber page={data.page} pages={data.pages} onChange={setPage} />
              </>
            ) : null}
          </QueryState>
        </Panel>
      </Stack>
    </Page>
  );
}

function ReportTable({ rows }: { rows: ReportSummary[] }) {
  return (
    <DataTable
      columns={[
        {
          label: "Date",
          render: (item) => (
            <Anchor component={AppLink} href={`/v2/reports/${item.date}/`}>
              {formatDate(item.date)}
            </Anchor>
          ),
        },
        {
          label: "Outlook",
          render: (item) => <DirectionBadge direction={safeDirection(item.prediction)} />,
        },
        { label: "Strength", render: (item) => item.strength ?? "—" },
      ]}
      rows={rows}
      rowKey={(item) => item.date}
      empty="No reports are available."
    />
  );
}

export function ReportDetailPage({ day }: { day: string }) {
  const query = useQuery(reportQuery(day));
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title={data ? `Report · ${formatDate(data.date)}` : "Report"}
        crumbs={[{ label: "Reports", to: "/v2/reports/" }, { label: day }]}
        actions={
          data?.older || data?.newer ? (
            <Group>
              {data.older ? (
                <Anchor component={AppLink} href={`/v2/reports/${data.older}/`}>
                  Older
                </Anchor>
              ) : null}
              {data.newer ? (
                <Anchor component={AppLink} href={`/v2/reports/${data.newer}/`}>
                  Newer
                </Anchor>
              ) : null}
            </Group>
          ) : undefined
        }
      />
      <QueryState pending={query.isPending} error={query.error} retry={() => void query.refetch()}>
        {data ? <ReportContent data={data} /> : null}
      </QueryState>
    </Page>
  );
}

function ReportContent({ data }: { data: ReportDetail }) {
  return (
    <Stack gap={12}>
      <KpiGrid cols={3}>
        <KpiTile label="Date" value={formatDate(data.date)} />
        <KpiTile
          label="Outlook"
          value={<DirectionBadge direction={safeDirection(data.prediction)} />}
        />
        <KpiTile
          label="Strength"
          value={data.strength ?? "—"}
          hint="Signal strength is not a probability."
        />
      </KpiGrid>
      <Panel title="Daily report">
        <Text style={{ whiteSpace: "pre-wrap" }} size="sm">
          {data.text || "No report text is available."}
        </Text>
      </Panel>
      <Panel title="Delivery history">
        <DataTable
          columns={[
            { label: "Channel", render: (delivery) => delivery.channel },
            { label: "Status", render: (delivery) => delivery.status_label },
            { label: "Attempt", render: (delivery) => formatTimestamp(delivery.created_at) },
            { label: "Diagnostic", render: (delivery) => delivery.error ?? "—" },
          ]}
          rows={data.deliveries}
          rowKey={(delivery) => delivery.id}
          empty="No recorded delivery attempts."
        />
      </Panel>
    </Stack>
  );
}

export function AccountPage() {
  const queryClient = useQueryClient();
  const query = useQuery(accountQuery());
  const data = query.data;
  const tokenMutation = useMutation({
    mutationFn: createToken,
    onSuccess: async (created) => {
      notifications.show({
        title: "Token created",
        message: `Copy this secret now: ${created.secret}`,
        autoClose: false,
      });
      await queryClient.invalidateQueries({ queryKey: ["app", "account"] });
    },
    onError: (error) =>
      notifications.show({ title: "Token not created", message: String(error), color: "red" }),
  });
  const revokeMutation = useMutation({
    mutationFn: revokeToken,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["app", "account"] }),
    onError: (error) =>
      notifications.show({ title: "Token not revoked", message: String(error), color: "red" }),
  });
  const [tokenName, setTokenName] = useState("");
  return (
    <Page>
      <PageHeader
        title="Account"
        description="Your persisted subscription, feature access, delivery preferences and API token metadata."
      />
      <QueryState pending={query.isPending} error={query.error} retry={() => void query.refetch()}>
        {data ? (
          <AccountContent
            data={data}
            tokenName={tokenName}
            setTokenName={setTokenName}
            createToken={(name) => tokenMutation.mutate(name)}
            creatingToken={tokenMutation.isPending}
            revokeToken={(id) => revokeMutation.mutate(id)}
          />
        ) : null}
      </QueryState>
    </Page>
  );
}

function AccountContent({
  data,
  tokenName,
  setTokenName,
  createToken: onCreateToken,
  creatingToken,
  revokeToken: onRevoke,
}: {
  data: Account;
  tokenName: string;
  setTokenName: (name: string) => void;
  createToken: (name: string) => void;
  creatingToken: boolean;
  revokeToken: (id: number) => void;
}) {
  const queryClient = useQueryClient();
  const [telegramUrl, setTelegramUrl] = useState("");
  const deliveryMutation = useMutation({
    mutationFn: (values: { email: boolean; telegram: boolean }) =>
      updateDelivery(values.email, values.telegram),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["app", "account"] }),
    onError: (error) =>
      notifications.show({
        title: "Delivery settings not saved",
        message: String(error),
        color: "red",
      }),
  });
  const telegramLink = useMutation({
    mutationFn: createTelegramLink,
    onSuccess: ({ url }) => setTelegramUrl(url),
    onError: (error) =>
      notifications.show({
        title: "Telegram link unavailable",
        message: String(error),
        color: "red",
      }),
  });
  const unlink = useMutation({
    mutationFn: unlinkTelegram,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["app", "account"] }),
    onError: (error) =>
      notifications.show({ title: "Telegram not unlinked", message: String(error), color: "red" }),
  });
  const verifyEmail = useMutation({
    mutationFn: sendEmailVerification,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["app", "account"] }),
    onError: (error) =>
      notifications.show({
        title: "Verification email not sent",
        message: String(error),
        color: "red",
      }),
  });
  return (
    <Stack gap={12}>
      <KpiGrid cols={4}>
        <KpiTile label="Account" value={data.username} hint={data.email} />
        <KpiTile
          label="Subscription"
          value={data.state}
          hint={data.ends_at ? `Ends ${formatTimestamp(data.ends_at)}` : "No end date recorded"}
        />
        <KpiTile
          label="Status"
          value={data.subscription_ok ? "Active" : "Restricted"}
          hint={data.required ? "Subscription required" : "No subscription requirement"}
        />
        <KpiTile
          label="API tokens"
          value={`${data.active_tokens}/${data.token_limit}`}
          hint={`Lifetime ${data.token_days} days`}
        />
      </KpiGrid>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Panel title="Feature access">
          <DataTable
            columns={[
              { label: "Feature", render: (feature) => feature.label },
              {
                label: "Access",
                render: (feature) => (
                  <Badge
                    color={feature.allowed ? "green" : feature.removed ? "gray" : "orange"}
                    variant="light"
                  >
                    {feature.removed ? "Removed" : feature.allowed ? "Available" : "Locked"}
                  </Badge>
                ),
              },
              { label: "Details", render: (feature) => feature.help },
            ]}
            rows={data.features}
            rowKey={(feature) => feature.key}
            empty="No feature access details."
          />
        </Panel>
        <Panel title="Report delivery">
          <Stack>
            <Text size="sm">
              {data.delivery.email_verified ? "Email verified" : "Email not verified"} ·{" "}
              {data.delivery.telegram_connected ? "Telegram connected" : "Telegram not connected"}
            </Text>
            <Group>
              <Checkbox
                label="Email reports"
                checked={data.delivery.email_reports}
                disabled={!data.delivery.email_verified || deliveryMutation.isPending}
                onChange={(event) =>
                  deliveryMutation.mutate({
                    email: event.currentTarget.checked,
                    telegram: data.delivery.telegram_reports,
                  })
                }
              />
              <Checkbox
                label="Telegram reports"
                checked={data.delivery.telegram_reports}
                disabled={!data.delivery.telegram_connected || deliveryMutation.isPending}
                onChange={(event) =>
                  deliveryMutation.mutate({
                    email: data.delivery.email_reports,
                    telegram: event.currentTarget.checked,
                  })
                }
              />
            </Group>
            {!data.delivery.email_verified ? (
              <Button
                variant="default"
                loading={verifyEmail.isPending}
                onClick={() => verifyEmail.mutate()}
              >
                Send verification email
              </Button>
            ) : null}
            {!data.delivery.telegram_connected ? (
              <Button
                variant="default"
                loading={telegramLink.isPending}
                onClick={() => telegramLink.mutate()}
              >
                Link Telegram
              </Button>
            ) : (
              <Button
                color="red"
                variant="light"
                loading={unlink.isPending}
                onClick={() => unlink.mutate()}
              >
                Unlink Telegram
              </Button>
            )}
            {telegramUrl ? (
              <Anchor href={telegramUrl} target="_blank" rel="noreferrer">
                Continue linking Telegram <LuExternalLink size={12} />
              </Anchor>
            ) : null}
          </Stack>
        </Panel>
      </SimpleGrid>
      <Panel
        title="API tokens"
        info="New token secrets are shown once and are never returned by later reads."
      >
        {data.api_enabled ? (
          <Stack gap={10}>
            <Group align="end">
              <TextInput
                label="Token name"
                value={tokenName}
                onChange={(event) => setTokenName(event.currentTarget.value)}
                maxLength={100}
              />
              <Button
                loading={creatingToken}
                disabled={!tokenName.trim()}
                onClick={() => onCreateToken(tokenName.trim())}
              >
                Create token
              </Button>
            </Group>
            <DataTable
              columns={[
                { label: "Name", render: (token) => token.name },
                { label: "Token", render: (token) => token.display },
                { label: "State", render: (token) => token.state },
                {
                  label: "Expires",
                  render: (token) => (token.expires_at ? formatTimestamp(token.expires_at) : "—"),
                },
                {
                  label: "Action",
                  render: (token) =>
                    token.state === "active" ? (
                      <Button
                        size="xs"
                        color="red"
                        variant="light"
                        onClick={() => onRevoke(token.id)}
                      >
                        Revoke
                      </Button>
                    ) : (
                      "—"
                    ),
                },
              ]}
              rows={data.tokens}
              rowKey={(token) => token.id}
              empty="No tokens have been created."
            />
          </Stack>
        ) : (
          <EmptyState
            title="API access is not enabled"
            description={
              data.api_docs
                ? "See API documentation for available access."
                : "No API token actions are available for this account."
            }
          />
        )}
      </Panel>
    </Stack>
  );
}

export function DeliveryPage() {
  const query = useQuery(deliveryQuery());
  const data = query.data;
  return (
    <Page>
      <PageHeader
        title="Delivery"
        description="Recorded report delivery attempts. Manage channels in Account settings."
        actions={
          <Anchor component={AppLink} href="/v2/account/">
            Account settings
          </Anchor>
        }
        meta={
          data ? (
            <Badge variant="light">{data.chat_count} configured Telegram chats</Badge>
          ) : undefined
        }
      />
      <Panel title="Recent delivery attempts">
        <QueryState
          pending={query.isPending}
          error={query.error}
          retry={() => void query.refetch()}
        >
          {data ? (
            <DataTable
              columns={[
                {
                  label: "Report",
                  render: (item) =>
                    item.report_date ? (
                      <Anchor component={AppLink} href={`/v2/reports/${item.report_date}/`}>
                        {formatDate(item.report_date)}
                      </Anchor>
                    ) : (
                      "Test / no report"
                    ),
                },
                { label: "Channel", render: (item) => item.channel },
                {
                  label: "Status",
                  render: (item) => (
                    <Badge color={item.status === "sent" ? "green" : "red"} variant="light">
                      {item.status_label}
                    </Badge>
                  ),
                },
                { label: "Attempted", render: (item) => formatTimestamp(item.created_at) },
                { label: "Diagnostic", render: (item) => item.error ?? "—" },
              ]}
              rows={data.items}
              rowKey={(item) => item.id}
              empty="No delivery attempts have been recorded."
            />
          ) : null}
        </QueryState>
      </Panel>
    </Page>
  );
}

export function OpsPage({ path = "ops/" }: { path?: string }) {
  const client = useQueryClient();
  const { data: session } = useSuspenseQuery(sessionQuery);
  const normalizedPath = path.replace(/^ops\/?/, "") || "overview/";
  const pagePath = normalizedPath.endsWith("/") ? normalizedPath : `${normalizedPath}/`;
  const [filters, setFilters] = useState<OpsSearch>(() => opsSearchSchema.parse({}));
  const [auditFilters, setAuditFilters] = useState<AuditSearch>({
    q: "",
    actor: "",
    action: "",
    page: 1,
    page_size: pageSize,
  });
  const [runsFilters, setRunsFilters] = useState<RunSearch>({
    q: "",
    label: "",
    status: "",
    trigger: "",
    page: 1,
    page_size: pageSize,
  });
  const detailRunId = pagePath.match(/^runs\/(\d+)\/$/)?.[1];
  const query = useQuery({ ...opsPageQuery(pagePath, filters), enabled: !detailRunId });
  const [pageData, setPageData] = useState<OpsPage | null>(null);
  const data = pageData ?? query.data;
  const audit = useQuery({
    ...auditQuery({
      ...auditFilters,
    }),
    enabled: pagePath === "audit/",
  });
  const runs = useQuery({
    ...runsQuery({
      ...runsFilters,
    }),
    enabled: pagePath === "runs/",
  });
  const detailRun = useQuery({
    ...runQuery(detailRunId ?? ""),
    enabled: Boolean(detailRunId),
  });
  if (!session.is_staff || (pagePath === "backups/" && !session.is_superuser)) {
    return (
      <Page>
        <ErrorState
          title="Operations access required"
          description="Your account does not have permission to view this operations page."
        />
      </Page>
    );
  }
  const isPending = detailRunId ? detailRun.isPending : query.isPending;
  const error = detailRunId ? detailRun.error : query.error;
  return (
    <Page>
      <PageHeader
        title={detailRun.data?.label ?? data?.title ?? "Operations"}
        description={data?.description}
        meta={<StatusBadge tone="caution">Staff workspace</StatusBadge>}
      />
      <QueryState
        pending={isPending}
        error={error}
        retry={() => void (detailRunId ? detailRun.refetch() : query.refetch())}
      >
        {data || detailRun.data ? (
          <OpsContent
            page={data ?? { title: "Task run", sections: [] }}
            audit={audit.data}
            runs={runs.data}
            runDetail={detailRun.data}
            filters={filters}
            setFilters={setFilters}
            auditFilters={auditFilters}
            setAuditFilters={setAuditFilters}
            runsFilters={runsFilters}
            setRunsFilters={setRunsFilters}
            onAction={async (form, body) => {
              const result = await submitOpsForm(form, body);
              result.messages.forEach((message) =>
                notifications.show({
                  title: message.level,
                  message: message.text,
                  color: message.level === "error" ? "red" : undefined,
                }),
              );
              if (result.page) setPageData(result.page);
              if (result.ok) {
                setPageData(null);
                await client.invalidateQueries({ queryKey: ["app", "ops"] });
                await client.invalidateQueries({ queryKey: ["app", "session"] });
              }
            }}
          />
        ) : null}
      </QueryState>
    </Page>
  );
}

function OpsContent({
  page,
  audit,
  runs,
  runDetail,
  filters,
  setFilters,
  auditFilters,
  setAuditFilters,
  runsFilters,
  setRunsFilters,
  onAction,
}: {
  page: OpsPage;
  audit?: OpsAuditPage;
  runs?: OpsRunPage;
  runDetail?: OpsRunDetail;
  filters: OpsSearch;
  setFilters: (filters: OpsSearch) => void;
  auditFilters: AuditSearch;
  setAuditFilters: (filters: AuditSearch) => void;
  runsFilters: RunSearch;
  setRunsFilters: (filters: RunSearch) => void;
  onAction: (form: OpsFormData, body: FormData) => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const stop = useMutation({
    mutationFn: stopRun,
    onSuccess: async (result) => {
      notifications.show({
        title: result.ok ? "Stop request accepted" : "Task was not stopped",
        message: result.status ?? "The server returned no additional status.",
        color: result.ok ? undefined : "red",
      });
      await queryClient.invalidateQueries({ queryKey: ["app", "ops"] });
    },
    onError: (error) =>
      notifications.show({ title: "Task was not stopped", message: String(error), color: "red" }),
  });
  const serverSection = page.sections.find((section) => section.table?.server);
  return (
    <Stack gap={12}>
      {serverSection && !audit && !runs ? (
        <Group align="end">
          <TextInput
            label={`Search ${page.title}`}
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.currentTarget.value, page: 1 })}
          />
          {(serverSection.table?.filters ?? []).map((key) => (
            <Select
              key={key}
              label={key}
              clearable
              value={String(filters[key as keyof OpsSearch] ?? "") || null}
              data={(serverSection.table?.filter_choices?.[key] ?? []).map((value) => ({
                value,
                label: value,
              }))}
              onChange={(value) =>
                setFilters({ ...filters, [key]: value ?? "", page: 1 } as OpsSearch)
              }
            />
          ))}
        </Group>
      ) : null}
      {audit || runs ? (
        <Group align="end">
          <TextInput
            label="Search"
            value={audit ? auditFilters.q : runsFilters.q}
            onChange={(event) =>
              audit
                ? setAuditFilters({ ...auditFilters, q: event.currentTarget.value, page: 1 })
                : setRunsFilters({ ...runsFilters, q: event.currentTarget.value, page: 1 })
            }
          />
          {audit ? (
            <>
              <Select
                label="Actor"
                clearable
                value={auditFilters.actor || null}
                data={audit.actors.map((actor) => ({ value: actor, label: actor }))}
                onChange={(value) =>
                  setAuditFilters({ ...auditFilters, actor: value ?? "", page: 1 })
                }
              />
              <Select
                label="Action"
                clearable
                value={auditFilters.action || null}
                data={audit.actions.map((action) => ({ value: action, label: action }))}
                onChange={(value) =>
                  setAuditFilters({ ...auditFilters, action: value ?? "", page: 1 })
                }
              />
            </>
          ) : null}
          {runs ? (
            <>
              <Select
                label="Status"
                clearable
                value={runsFilters.status || null}
                data={["pending", "started", "success", "failure"].map((status) => ({
                  value: status,
                  label: status,
                }))}
                onChange={(value) =>
                  setRunsFilters({
                    ...runsFilters,
                    status: (value ?? "") as RunSearch["status"],
                    page: 1,
                  })
                }
              />
              <Select
                label="Trigger"
                clearable
                value={runsFilters.trigger || null}
                data={[
                  { value: "auto", label: "Automatic" },
                  { value: "manual", label: "Manual" },
                ]}
                onChange={(value) =>
                  setRunsFilters({
                    ...runsFilters,
                    trigger: (value ?? "") as RunSearch["trigger"],
                    page: 1,
                  })
                }
              />
              <Select
                label="Task"
                clearable
                value={runsFilters.label || null}
                data={runs.labels.map((label) => ({ value: label, label }))}
                onChange={(value) =>
                  setRunsFilters({ ...runsFilters, label: value ?? "", page: 1 })
                }
              />
            </>
          ) : null}
        </Group>
      ) : null}
      {runDetail ? (
        <Panel
          title={runDetail.label}
          actions={
            runDetail.is_active ? (
              <Button
                color="red"
                variant="light"
                loading={stop.isPending}
                onClick={() => {
                  if (window.confirm(`Request that ${runDetail.label} stop?`)) {
                    stop.mutate(String(runDetail.id));
                  }
                }}
              >
                Request stop
              </Button>
            ) : undefined
          }
        >
          <Stack>
            <Text size="sm">
              {runDetail.status_label} · {runDetail.trigger}
            </Text>
            <Text size="xs" c="dimmed">
              {runDetail.error || "No recorded error"}
            </Text>
            {runDetail.output ? (
              <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                {runDetail.output}
              </Text>
            ) : null}
          </Stack>
        </Panel>
      ) : null}
      {audit ? (
        <Panel title="Audit trail">
          <DataTable
            columns={[
              { label: "Time", render: (row) => formatTimestamp(row.created_at) },
              { label: "Actor", render: (row) => row.actor_name },
              { label: "Action", render: (row) => row.action },
              { label: "Target", render: (row) => row.target },
              { label: "Detail", render: (row) => row.detail },
              { label: "IP", render: (row) => row.ip_address ?? "—" },
            ]}
            rows={audit.items}
            rowKey={(row) => row.id}
            empty="No audit events."
          />
          <PageNumber
            page={audit.page}
            pages={audit.pages}
            onChange={(page) => setAuditFilters({ ...auditFilters, page })}
          />
        </Panel>
      ) : null}
      {runs ? (
        <Panel title="Task runs">
          <DataTable
            columns={[
              {
                label: "Task",
                render: (row) => (
                  <Anchor component={AppLink} href={`/v2/ops/runs/${row.id}/`}>
                    {row.label}
                  </Anchor>
                ),
              },
              { label: "Status", render: (row) => row.status_label },
              { label: "Trigger", render: (row) => row.trigger },
              {
                label: "Started",
                render: (row) => (row.started_at ? formatTimestamp(row.started_at) : "—"),
              },
              {
                label: "Duration",
                render: (row) =>
                  row.duration_ms == null ? "—" : `${formatNumber(row.duration_ms / 1000, 1)}s`,
              },
            ]}
            rows={runs.items}
            rowKey={(row) => row.id}
            empty="No retained task runs."
          />
          <PageNumber
            page={runs.page}
            pages={runs.pages}
            onChange={(page) => setRunsFilters({ ...runsFilters, page })}
          />
        </Panel>
      ) : null}
      {page.sections.map((section, index) => (
        <Panel key={`${section.title}-${index}`} title={section.title}>
          {section.description ? (
            <Text size="sm" c="dimmed" mb="sm">
              {section.description}
            </Text>
          ) : null}
          {section.details ? <OpsDetails values={section.details} /> : null}
          {section.chart?.length ? (
            <DataTable
              columns={[
                { label: "Date", render: (point) => point.label },
                { label: "Value", render: (point) => point.value },
                { label: "Failed", render: (point) => point.failed },
              ]}
              rows={section.chart}
              rowKey={(point) => point.label}
              empty="No chart data."
            />
          ) : null}
          {section.table && !((audit || runs) && section.table.server) ? (
            <OpsDynamicTable
              section={section}
              filters={filters}
              setFilters={setFilters}
              onAction={onAction}
            />
          ) : null}
          {section.links?.length ? (
            <Group>
              {section.links.map((link) => (
                <Anchor
                  key={link.url}
                  component={AppLink}
                  href={`/v2/${link.url.replace(/^\/+/, "")}`}
                >
                  {link.label}
                </Anchor>
              ))}
            </Group>
          ) : null}
          {section.forms?.length ? (
            <Stack gap={8} mt="sm">
              {section.forms.map((form) => (
                <OpsFormView key={form.id} form={form} onSubmit={onAction} />
              ))}
            </Stack>
          ) : null}
        </Panel>
      ))}
    </Stack>
  );
}

function OpsDetails({ values }: { values: Record<string, OpsCell> }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} mb="sm">
      {Object.entries(values).map(([label, cell]) => (
        <div key={label}>
          <Text size="xs" c="dimmed">
            {label}
          </Text>
          {cell.href ? (
            <Anchor href={cell.href}>{cell.text}</Anchor>
          ) : (
            <Text size="sm">{cell.text}</Text>
          )}
        </div>
      ))}
    </SimpleGrid>
  );
}

function OpsDynamicTable({
  section,
  filters,
  setFilters,
  onAction,
}: {
  section: OpsPage["sections"][number];
  filters: OpsSearch;
  setFilters: (filters: OpsSearch) => void;
  onAction: (form: OpsFormData, body: FormData) => Promise<void>;
}) {
  const table = section.table;
  if (!table) return null;
  return (
    <>
      <DataTable<OpsRow>
        columns={table.columns.map((column) => ({
          label: column.label,
          render: (row: OpsRow) => {
            const cell = row.cells[column.key];
            return cell?.href ? <Anchor href={cell.href}>{cell.text}</Anchor> : (cell?.text ?? "—");
          },
        }))}
        rows={table.rows}
        rowKey={(row) =>
          Object.values(row.cells)
            .map((cell) => cell.text)
            .join("-")
        }
        empty={`No ${section.title.toLowerCase()} data.`}
      />
      {table.server && table.pages && table.pages > 1 ? (
        <PageNumber
          page={table.page ?? 1}
          pages={table.pages}
          onChange={(page) => setFilters({ ...filters, page })}
        />
      ) : null}
      {table.rows.map((row, index) =>
        row.forms?.length ? (
          <Group key={index}>
            {row.forms.map((form) => (
              <OpsFormView key={form.id} form={form} onSubmit={onAction} />
            ))}
          </Group>
        ) : null,
      )}
    </>
  );
}

function OpsFormView({
  form,
  onSubmit,
}: {
  form: OpsFormData;
  onSubmit: (form: OpsFormData, body: FormData) => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.disabled || pending) return;
    if (form.confirmation && !window.confirm(form.confirmation)) return;
    setPending(true);
    try {
      await onSubmit(form, new FormData(event.currentTarget));
    } catch (error) {
      notifications.show({ title: "Action failed", message: String(error), color: "red" });
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={(event) => void submit(event)}>
      <Group align="end">
        <Stack gap={4}>
          {form.fields?.map((field) => (
            <OpsFieldInput key={field.name} field={field} />
          ))}
          {form.errors?.map((error) => (
            <Text key={error} c="red" size="xs">
              {error}
            </Text>
          ))}
        </Stack>
        <Button type="submit" loading={pending} disabled={form.disabled}>
          {form.label}
        </Button>
      </Group>
    </form>
  );
}

function OpsFieldInput({ field }: { field: OpsFieldData }) {
  const common = {
    name: field.name,
    required: field.required,
    min: field.min ?? undefined,
    max: field.max ?? undefined,
  };
  if (field.kind === "hidden")
    return <input type="hidden" name={field.name} value={field.value ?? ""} />;
  let input: ReactNode;
  if (field.kind === "checkbox") {
    input = <Checkbox name={field.name} label={field.label} defaultChecked={field.checked} />;
  } else if (field.kind === "textarea") {
    input = (
      <Textarea
        {...common}
        label={field.label}
        defaultValue={field.value}
        description={field.help}
      />
    );
  } else if (field.kind === "select") {
    input = (
      <Select
        name={field.name}
        label={field.label}
        required={field.required}
        defaultValue={field.value ?? null}
        data={(field.choices ?? []).map((choice) => ({ value: choice.value, label: choice.label }))}
      />
    );
  } else if (field.kind === "password") {
    input = <PasswordInput {...common} label={field.label} defaultValue={field.value} />;
  } else if (field.kind === "number") {
    input = (
      <NumberInput
        name={field.name}
        label={field.label}
        defaultValue={field.value ? Number(field.value) : undefined}
        min={field.min ? Number(field.min) : undefined}
        max={field.max ? Number(field.max) : undefined}
        step={field.step ? Number(field.step) : undefined}
        required={field.required}
      />
    );
  } else if (field.kind === "file") {
    input = (
      <label>
        <Text size="xs" fw={500}>
          {field.label}
        </Text>
        <input name={field.name} type="file" required={field.required} />
      </label>
    );
  } else {
    input = (
      <TextInput
        {...common}
        type={field.kind === "date" || field.kind === "time" ? field.kind : "text"}
        label={field.label}
        defaultValue={field.value}
        description={field.help}
        maxLength={field.max_length ?? undefined}
      />
    );
  }
  return (
    <Stack gap={2}>
      {input}
      {field.errors?.map((error) => (
        <Text key={error} size="xs" c="red">
          {error}
        </Text>
      ))}
    </Stack>
  );
}

export function LoginForm() {
  const csrf = csrfToken() ?? "";
  const [pending, setPending] = useState(false);
  const next = new URLSearchParams(window.location.search).get("next") ?? "/v2/";
  return (
    <form method="post" action="/login/" onSubmit={() => setPending(true)}>
      <input type="hidden" name="csrfmiddlewaretoken" value={csrf} />
      <input type="hidden" name="next" value={next} />
      <Stack gap={12}>
        <TextInput
          name="username"
          label="User name"
          autoComplete="username"
          required
          maxLength={150}
        />
        <PasswordInput name="password" label="Password" autoComplete="current-password" required />
        <Button type="submit" loading={pending}>
          Log in
        </Button>
        <Text size="xs" c="dimmed" ta="center">
          New here? <Anchor href="/signup/">Continue to secure signup</Anchor>
        </Text>
      </Stack>
    </form>
  );
}

export function LoginPage() {
  return (
    <AuthPage title="Log in" description="Sign in with your existing Kash Engine account.">
      <LoginForm />
    </AuthPage>
  );
}

export function SignupPage() {
  return (
    <AuthPage
      title="Create your account"
      description="Account registration is handled by the existing Django signup flow."
    >
      <Button component="a" href="/signup/">
        Continue to secure signup
      </Button>
    </AuthPage>
  );
}

function AuthPage({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Page>
      <Stack maw={440} mx="auto" mt={48} gap={16}>
        <PageHeader title={title} description={description} />
        <Panel title="Secure account access">{children}</Panel>
        <Text size="xs" c="dimmed" ta="center">
          Account actions are processed by Kash Engine's existing Django authentication flow.
        </Text>
      </Stack>
    </Page>
  );
}
