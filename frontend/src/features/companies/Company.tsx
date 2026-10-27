import {
  Accordion,
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  LuActivity,
  LuArrowDownRight,
  LuArrowLeft,
  LuArrowUpRight,
  LuBuilding2,
  LuChartNoAxesCombined,
  LuExternalLink,
  LuInfo,
  LuLayers,
  LuMinus,
  LuNewspaper,
  LuTrendingDown,
  LuTrendingUp,
} from "react-icons/lu";

import type {
  CompanyBar,
  CompanyDetail,
  CompanyPrice,
  CompanyStory,
} from "../../shared/api/generated/types.gen";
import { useLiveQuotes } from "../../shared/api/liveQuotes";
import { DataTable } from "../../shared/ui/DataTable";
import type { TableColumn } from "../../shared/ui/DataTable";
import { LiveCompanyQuote, LivePrice } from "../../shared/ui/LiveMarket";
import { SavedFacts } from "../../shared/ui/SavedFacts";
import { sourceLink } from "../../shared/ui/sourceLink";
import { CandlestickTrendChart } from "../../shared/ui/TanStackCharts";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { CompanyTradeSetups } from "./CompanyTradeSetups";
import { PredictionReview } from "./PredictionReview";
import { CompanyValuation } from "./CompanyValuation";
import { collectFacts, comparableNumber, humanize } from "./fundamentalFacts";
import { projectClosingPrices } from "./predictionAnalysis";
export { projectClosingPrices } from "./predictionAnalysis";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const date = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "medium",
});
export function savedTime(value: string) {
  return date.format(new Date(value));
}
export function score(value: number | null) {
  return value === null ? "Not scored" : value.toFixed(3);
}

export function QuoteFreshness({ quote }: { quote: CompanyPrice }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, []);
  const stale = now - Date.parse(quote.as_of) > (quote.mode === "stream" ? 15_000 : 600_000);
  return (
    <Group gap="xs" align="center" className="company-quote-freshness">
      <span
        className={`company-freshness-dot ${stale ? "is-stale" : "is-live"}`}
        aria-hidden="true"
      />
      <Text size="sm" c={stale ? "dimmed" : undefined}>
        {quote.mode === "stream" ? "Stream observation" : "Scheduled snapshot"}
        {stale ? " - older observation, not live" : ""}
        {" | "}
        <time dateTime={quote.as_of}>{savedTime(quote.as_of)} IST</time>
      </Text>
    </Group>
  );
}

export function PriceSummary({ quote }: { quote: CompanyPrice | null }) {
  if (!quote)
    return (
      <Text c="dimmed">
        No saved quote. Configure the company's instrument key and run ingestion.
      </Text>
    );
  return (
    <Stack gap="xs" className="company-quote-summary">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
        <div className="company-quote-metric">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Last price
          </Text>
          <Title order={3}>INR {number.format(quote.price)}</Title>
        </div>
        <div className="company-quote-metric">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Change
          </Text>
          <Group gap={4} align="center">
            {quote.change_pct !== null &&
              (quote.change_pct >= 0 ? (
                <LuArrowUpRight aria-hidden="true" />
              ) : (
                <LuArrowDownRight aria-hidden="true" />
              ))}
            <Text
              fw={600}
              c={quote.change_pct === null ? "dimmed" : quote.change_pct >= 0 ? "teal" : "red"}
            >
              {quote.change_pct === null ? "Not available" : `${number.format(quote.change_pct)}%`}
            </Text>
          </Group>
        </div>
        <div className="company-quote-metric">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Previous close
          </Text>
          <Text fw={600}>
            {quote.previous_close === null
              ? "Not available"
              : `INR ${number.format(quote.previous_close)}`}
          </Text>
        </div>
        <div className="company-quote-metric">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Volume
          </Text>
          <Text fw={600}>
            {quote.volume === null ? "Not supplied" : number.format(quote.volume)}
          </Text>
        </div>
      </SimpleGrid>
      <QuoteFreshness quote={quote} />
    </Stack>
  );
}

function PriceTrend({ candles }: { candles: CompanyBar[] }) {
  if (!candles.length)
    return (
      <Text c="dimmed">
        No saved daily price history. At least 20 saved daily closes are needed to show a
        projection.
      </Text>
    );
  const projection = projectClosingPrices(candles);
  const projectionPoints = projection.map(({ label, value }) => ({ label, value }));
  return (
    <Stack gap="md">
      <Group className="company-chart-legend" gap="md" wrap="wrap">
        <Text size="xs">
          <span className="company-chart-key company-chart-key-up" /> Up session
        </Text>
        <Text size="xs">
          <span className="company-chart-key company-chart-key-down" /> Down session
        </Text>
        <Text size="xs">
          <span className="company-chart-key company-chart-key-projection" /> History-only
          projection
        </Text>
      </Group>
      <CandlestickTrendChart
        candles={candles.map((bar) => ({ ...bar, label: bar.day }))}
        projectionPoints={projectionPoints}
        ariaLabel="Daily candlestick chart; each candle shows open, high, low and close in INR"
        height={440}
      />
      <div className="company-chart-note">
        <Text c="dimmed" size="sm">
          Each candle shows open, high, low and close in INR. The dashed line extends a linear fit
          of the latest 20 closes across 20 future sessions; it is not a price target or financial
          advice. Historical simulation results below do not validate future performance; splits or
          dividends can distort it.
        </Text>
      </div>
      {projection.length === 0 && (
        <Text c="dimmed">At least 20 saved daily closes are needed to show a projection.</Text>
      )}
      <Accordion variant="separated">
        <Accordion.Item value="history">
          <Accordion.Control>Daily OHLCV history ({candles.length} sessions)</Accordion.Control>
          <Accordion.Panel>
            <DataTable
              data={candles}
              label="Daily OHLCV history"
              columns={barColumns}
              initialSort={[{ id: "day", desc: true }]}
            />
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

const barColumns: TableColumn<CompanyBar>[] = [
  { id: "day", label: "Day", value: (bar) => bar.day },
  ...(["open", "high", "low", "close", "volume"] as const).map((key) => ({
    id: key,
    label: key[0].toUpperCase() + key.slice(1),
    value: (bar: CompanyBar) => bar[key],
    render: (bar: CompanyBar) => number.format(bar[key]),
  })),
];

export function metricAssessment(label: string, value: unknown, comparison: unknown) {
  const actual = comparableNumber(value);
  const sector = comparableNumber(comparison);
  if (actual === null) return { label: "Not assessable", color: "gray" };
  if (sector === null) return { label: "No sector benchmark", color: "gray" };

  const key = label.toLowerCase();
  const profitability =
    /roe|roce|return on|profit margin|operating margin|net margin|revenue growth|earnings growth|eps growth|interest coverage/.test(
      key,
    );
  const leverage = /debt.*equity|debt ratio|gearing|leverage/.test(key);
  const valuation =
    /p\/e|price.*earnings|p\/b|price.*book|ev\s*\/\s*ebitda|valuation multiple/.test(key);
  const above = actual > sector;

  if ((leverage && (actual < 0 || sector < 0)) || (valuation && (actual <= 0 || sector <= 0)))
    return { label: "Not comparable · context needed", color: "gray" };
  if (actual === sector) return { label: "In line with sector", color: "gray" };
  if (profitability)
    return above
      ? { label: "Favorable · stronger vs sector", color: "teal" }
      : { label: "Unfavorable · weaker vs sector", color: "orange" };
  if (leverage)
    return above
      ? { label: "Unfavorable · higher leverage", color: "orange" }
      : { label: "Favorable · lower leverage", color: "teal" };
  if (valuation)
    return { label: `${above ? "Higher" : "Lower"} multiple · context needed`, color: "yellow" };
  return { label: `${above ? "Above" : "Below"} sector · context needed`, color: "gray" };
}

function factDescription(label: string) {
  const key = label.toLowerCase();
  if (/price to earnings|\bp\/e\b/.test(key))
    return "Price relative to earnings per share. Compare with peers and growth; a high or low ratio is not meaningful on its own.";
  if (/price to book|\bp\/b\b/.test(key))
    return "Price relative to book value per share. Interpretation varies by sector and asset mix.";
  if (/return on equity|\broe\b/.test(key))
    return "Profit generated relative to shareholder equity. Leverage and one-off items can affect this measure.";
  if (/debt to equity/.test(key))
    return "Total debt relative to shareholder equity. Capital needs differ substantially across industries.";
  if (/market cap|market capitalization/.test(key))
    return "The market value of the company's listed equity, not the sector's market capitalization.";
  if (/dividend yield/.test(key))
    return "Annual dividend relative to share price. Past distributions do not guarantee future dividends.";
  return `Reported ${humanize(label)}. Check its unit, reporting period and sector context before comparing. A sector comparison alone does not establish investment quality.`;
}

function factValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "number")
    return Number.isFinite(value) ? number.format(value) : "Not available";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function Fundamentals({ data }: { data: CompanyDetail }) {
  const categories = Object.entries(data.fundamentals)
    .map(([key, value]) => ({ label: humanize(key), facts: collectFacts(value) }))
    .filter((category) => category.facts.length > 0);

  if (!categories.length) return <Text c="dimmed">No saved fundamentals.</Text>;

  const facts = categories.flatMap((category) =>
    category.facts.map((fact) => ({
      ...fact,
      category: category.label,
      assessment: metricAssessment(fact.label, fact.value, fact.comparison),
    })),
  );
  type Row = (typeof facts)[number];
  const columns: TableColumn<Row>[] = [
    {
      id: "metric",
      label: "Metric",
      value: (fact) => humanize(fact.label),
      render: (fact) => (
        <Group gap="xs" wrap="nowrap">
          <Text size="sm" fw={600}>
            {humanize(fact.label)}
          </Text>
          <Tooltip label={factDescription(fact.label)} multiline w={280} withArrow>
            <ActionIcon variant="subtle" size="sm" aria-label={`About ${humanize(fact.label)}`}>
              <LuInfo aria-hidden="true" />
            </ActionIcon>
          </Tooltip>
        </Group>
      ),
    },
    {
      id: "value",
      label: "Company value",
      value: (fact) => comparableNumber(fact.value) ?? factValue(fact.value),
      render: (fact) => factValue(fact.value),
    },
    {
      id: "sector",
      label: "Sector benchmark",
      value: (fact) => comparableNumber(fact.comparison),
      render: (fact) => factValue(fact.comparison),
    },
    {
      id: "assessment",
      label: "Assessment",
      value: (fact) => fact.assessment.label,
      render: (fact) => (
        <Badge variant="light" color={fact.assessment.color}>
          {fact.assessment.label}
        </Badge>
      ),
    },
    { id: "category", label: "Category", value: (fact) => fact.category },
  ];
  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        Favorable/unfavorable compares a metric with its supplied sector benchmark, not the stock's
        overall investment quality. Lower valuation multiples are not automatically better. Missing
        benchmarks, units or periods require context.
      </Text>
      <DataTable
        data={facts}
        columns={columns}
        label="Fundamental metrics"
        filters={[
          {
            label: "Category",
            value: (fact) => fact.category,
            options: categories.map((category) => category.label),
          },
          {
            label: "Assessment",
            value: (fact) => fact.assessment.label,
            options: [...new Set(facts.map((fact) => fact.assessment.label))],
          },
        ]}
      />
    </Stack>
  );
}

function companyNewsSentiment(value: number | null) {
  if (value === null) return { label: "Not scored", color: "gray" };
  if (value > 0) return { label: `Positive · ${number.format(value)}`, color: "teal" };
  if (value < 0) return { label: `Negative · ${number.format(value)}`, color: "red" };
  return { label: "Neutral · 0", color: "gray" };
}

const companyNewsColumns: TableColumn<CompanyStory>[] = [
  {
    id: "title",
    label: "Article & context",
    value: (story) => story.title,
    render: (story) => {
      const href = sourceLink(story.url);
      return (
        <div className="table-story">
          <div className="table-primary">
            {href ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {story.title}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            ) : (
              story.title
            )}
          </div>
          {story.sentiment_reason && (
            <Text size="sm" mt="xs">
              {story.sentiment_reason}
            </Text>
          )}
        </div>
      );
    },
  },
  { id: "source", label: "Source", value: (story) => story.source },
  {
    id: "published_at",
    label: "Published",
    value: (story) => story.published_at,
    render: (story) =>
      story.published_at ? (
        <time dateTime={story.published_at}>{savedTime(story.published_at)} IST</time>
      ) : (
        "Not available"
      ),
  },
  {
    id: "sentiment_score",
    label: "Sentiment",
    value: (story) => story.sentiment_score,
    render: (story) => {
      const sentiment = companyNewsSentiment(story.sentiment_score);
      return (
        <Badge size="sm" variant="light" color={sentiment.color}>
          {sentiment.label}
        </Badge>
      );
    },
  },
  {
    id: "relevance",
    label: "Relevance",
    value: (story) => story.relevance,
    render: (story) =>
      story.relevance === null ? "Not available" : number.format(story.relevance),
  },
];

export function CompanyView({ data }: { data: CompanyDetail }) {
  usePageTitle(data.company.name);

  const hasMarkets = data.markets_available;
  const hasNews = data.news_available;
  const hasIpos = data.ipos_available;
  const streamable = hasMarkets && Boolean(data.instrument_key);
  const live = useLiveQuotes(streamable ? [data.company.id] : [], streamable);
  const liveQuote = live.companies.get(data.company.id);
  const previousClose = liveQuote?.previous_close ?? data.quote?.previous_close ?? null;
  const volume = liveQuote?.volume ?? data.quote?.volume ?? null;

  return (
    <Stack gap="xl" className="company-page-root">
      {/* 1. Modern Header / Hero Section */}
      <header className="company-header-hero">
        <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="xs">
          <Anchor component={Link} to="/companies/" className="company-back-link">
            <LuArrowLeft aria-hidden="true" />
            <span>Companies</span>
          </Anchor>
          {data.company.screener_url && sourceLink(data.company.screener_url) && (
            <Anchor
              href={sourceLink(data.company.screener_url)!}
              target="_blank"
              rel="noopener noreferrer"
              className="company-screener-link"
            >
              <span>Screener</span>
              <LuExternalLink aria-hidden="true" />
              <span className="sr-only"> (opens in a new tab)</span>
            </Anchor>
          )}
        </Group>

        <Group justify="space-between" align="flex-end" wrap="wrap" gap="md">
          <div className="company-identity">
            <Title order={1} className="company-title">
              {data.company.name}
            </Title>
            <Group gap="xs" mt="xs" wrap="wrap" align="center">
              <Badge size="md" variant="filled" color="violet">
                {data.company.symbol}
              </Badge>
              <Badge size="md" variant="light" color="gray">
                {data.company.sector || "Sector not available"}
              </Badge>
              {data.instrument_key && (
                <Badge size="md" variant="outline" color="gray" className="company-key-badge">
                  Key: {data.instrument_key}
                </Badge>
              )}
            </Group>
            {liveQuote && (
              <div className="company-hero-live" aria-label="Live price">
                <LivePrice quote={liveQuote} />
              </div>
            )}
            <Text size="xs" c="dimmed" mt="xs">
              {data.company.symbol} | {data.company.sector || "Sector not available"}
            </Text>
            <Text size="xs" c="dimmed">
              {data.instrument_key || "No instrument mapping configured."}
            </Text>
          </div>
        </Group>
      </header>

      {/* 2. System Alerts / Section Refresh Errors */}
      {Object.entries(data.errors).map(([section, message]) => (
        <Alert key={section} color="orange" title={`${section} refresh failed`}>
          {message} Previously saved data is retained.
        </Alert>
      ))}

      {/* 3. At-a-Glance Snapshot KPI Row */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: hasMarkets && data.outlook ? 4 : 3 }} spacing="md">
        {/* KPI Card 1: Trading session / Company profile */}
        {hasMarkets && data.quote ? (
          <Paper p="md" withBorder className="company-stat-card">
            <Group justify="space-between" align="center">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                Trading Session
              </Text>
              <LuActivity className="company-stat-icon" aria-hidden="true" />
            </Group>
            <div>
              <Text size="sm" c="dimmed">
                Previous close:{" "}
                <Text component="span" fw={600} c="var(--brand-ink)">
                  {previousClose !== null ? `INR ${number.format(previousClose)}` : "Not available"}
                </Text>
              </Text>
              <Text size="sm" c="dimmed" mt={4}>
                Volume:{" "}
                <Text component="span" fw={600} c="var(--brand-ink)">
                  {volume !== null ? number.format(volume) : "Not supplied"}
                </Text>
              </Text>
            </div>
            <Group justify="space-between" mt="xs" pt="xs" className="company-stat-subrow">
              <Text size="xs" c="dimmed">
                Observation:{" "}
                {liveQuote
                  ? "Live stream"
                  : data.quote.mode === "stream"
                    ? "Realtime stream"
                    : "Scheduled snapshot"}
              </Text>
            </Group>
          </Paper>
        ) : (
          <Paper p="md" withBorder className="company-stat-card">
            <Group justify="space-between" align="center">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                Company Profile
              </Text>
              <LuBuilding2 className="company-stat-icon" aria-hidden="true" />
            </Group>
            <div>
              <Text size="sm" fw={600}>
                {data.company.sector || "Unclassified Sector"}
              </Text>
              <Text size="xs" c="dimmed" mt={4}>
                {data.instrument_key ? "Instrument configured" : "No instrument key mapped"}
              </Text>
            </div>
            <Group justify="space-between" mt="xs" pt="xs" className="company-stat-subrow">
              <Text size="xs" c="dimmed">
                Symbol: {data.company.symbol}
              </Text>
            </Group>
          </Paper>
        )}

        {/* KPI Card 2: Engine Outlook / Direction Signal */}
        {hasMarkets && data.outlook && (
          <Paper p="md" withBorder className="company-stat-card">
            <Group justify="space-between" align="center">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                Engine Outlook
              </Text>
              <span className="report-outlook" data-tone={data.outlook.direction}>
                {data.outlook.direction === "up" ? (
                  <LuTrendingUp aria-hidden="true" />
                ) : data.outlook.direction === "down" ? (
                  <LuTrendingDown aria-hidden="true" />
                ) : (
                  <LuMinus aria-hidden="true" />
                )}{" "}
                {data.outlook.direction === "up"
                  ? "Bullish"
                  : data.outlook.direction === "down"
                    ? "Bearish"
                    : "Neutral"}
              </span>
            </Group>
            <div>
              <Text size="sm" fw={600}>
                Signal Score: {score(data.outlook.score)}
              </Text>
              <Text size="xs" c="dimmed" mt={2}>
                Target: {data.outlook.target_date}
              </Text>
            </div>
            <Group justify="space-between" mt="xs" pt="xs" className="company-stat-subrow">
              <Text size="xs" c="dimmed">
                Momentum: {score(data.outlook.momentum_score)}
              </Text>
              <Text size="xs" c="dimmed">
                News: {data.outlook.news_score !== null ? score(data.outlook.news_score) : "None"}
              </Text>
            </Group>
          </Paper>
        )}

        {/* KPI Card 3: News Sentiment */}
        {hasNews && (
          <Paper p="md" withBorder className="company-stat-card">
            <Group justify="space-between" align="center">
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                News Sentiment
              </Text>
              <LuNewspaper className="company-stat-icon" aria-hidden="true" />
            </Group>
            <div>
              <Text size="lg" fw={700}>
                {data.news.length} {data.news.length === 1 ? "article" : "articles"}
              </Text>
              <Text size="xs" c="dimmed" mt={2}>
                {data.news.length > 0 ? "Latest market coverage" : "No linked coverage"}
              </Text>
            </div>
            {data.news.length > 0 ? (
              <Group gap="xs" mt="xs" pt="xs" className="company-stat-subrow">
                <Badge size="xs" variant="light" color="teal">
                  {
                    data.news.filter((s) => s.sentiment_score !== null && s.sentiment_score > 0)
                      .length
                  }{" "}
                  Positive
                </Badge>
                <Badge size="xs" variant="light" color="gray">
                  {
                    data.news.filter((s) => s.sentiment_score === null || s.sentiment_score === 0)
                      .length
                  }{" "}
                  Neutral
                </Badge>
                <Badge size="xs" variant="light" color="red">
                  {
                    data.news.filter((s) => s.sentiment_score !== null && s.sentiment_score < 0)
                      .length
                  }{" "}
                  Negative
                </Badge>
              </Group>
            ) : (
              <Group mt="xs" pt="xs" className="company-stat-subrow">
                <Text size="xs" c="dimmed">
                  No sentiment feed
                </Text>
              </Group>
            )}
          </Paper>
        )}

        {/* KPI Card 4: Data & Records Availability */}
        <Paper p="md" withBorder className="company-stat-card">
          <Group justify="space-between" align="center">
            <Text size="xs" c="dimmed" fw={600} tt="uppercase">
              Fundamentals &amp; Records
            </Text>
            <LuLayers className="company-stat-icon" aria-hidden="true" />
          </Group>
          <div>
            <Text size="sm">
              <Text component="span" c="dimmed">
                Last saved:{" "}
              </Text>
              <Text component="span" fw={600}>
                {data.fundamentals_as_of
                  ? savedTime(data.fundamentals_as_of) + " IST"
                  : "Not available"}
              </Text>
            </Text>
            <Text size="sm" mt={2}>
              <Text component="span" c="dimmed">
                Price history:{" "}
              </Text>
              <Text component="span" fw={600}>
                {data.candles.length} sessions
              </Text>
            </Text>
          </div>
          <Group justify="space-between" mt="xs" pt="xs" className="company-stat-subrow">
            <Text size="xs" c="dimmed">
              IPO scores: {data.ipos.length ? `${data.ipos.length} recorded` : "None"}
            </Text>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* 4. Quick-Jump In-Page Nav Bar */}
      <nav aria-label="Company sections" className="company-section-nav">
        {hasMarkets && (
          <a href="#market-panel" className="company-nav-pill">
            <LuChartNoAxesCombined aria-hidden="true" />
            <span>Market &amp; Trend</span>
          </a>
        )}
        {hasMarkets && (
          <a href="#prediction-review" className="company-nav-pill">
            <LuActivity aria-hidden="true" />
            <span>Prediction accuracy</span>
          </a>
        )}
        <a href="#company-summary" className="company-nav-pill">
          <LuBuilding2 aria-hidden="true" />
          <span>About</span>
        </a>
        <a href="#fundamentals" className="company-nav-pill">
          <LuActivity aria-hidden="true" />
          <span>Fundamentals</span>
        </a>
        <a href="#company-valuation" className="company-nav-pill">
          <LuLayers aria-hidden="true" />
          <span>Valuation</span>
        </a>
        {hasNews && (
          <a href="#company-news" className="company-nav-pill">
            <LuNewspaper aria-hidden="true" />
            <span>News ({data.news.length})</span>
          </a>
        )}
        {hasIpos && data.ipos.length > 0 && (
          <a href="#company-ipos" className="company-nav-pill">
            <LuLayers aria-hidden="true" />
            <span>IPOs ({data.ipos.length})</span>
          </a>
        )}
      </nav>

      {/* 5. Company Summary / Business Overview Card */}
      <Paper id="company-summary" p="lg" withBorder className="company-summary-card">
        <Group gap="xs" mb="sm" align="center">
          <LuBuilding2 className="company-summary-icon" aria-hidden="true" />
          <Title order={2} size="h3">
            Company summary
          </Title>
        </Group>
        <Text className="company-summary-text">
          {data.summary || "No provider business summary has been saved yet."}
        </Text>
      </Paper>

      {/* 6. Market Price & Trend Section */}
      {hasMarkets ? (
        <Paper id="market-panel" p="lg" withBorder className="company-market-panel">
          <Group justify="space-between" align="flex-start" mb="md" gap="md" wrap="wrap">
            <div>
              <Title order={2} size="h3">
                Market price &amp; trend
              </Title>
              <Text size="sm" c="dimmed">
                Daily OHLC candles with a history-only projection.
              </Text>
            </div>
            {!liveQuote && <PriceSummary quote={data.quote} />}
          </Group>
          {liveQuote && (
            <LiveCompanyQuote quote={liveQuote} connection={live.connection} status={live.status} />
          )}
          <PriceTrend candles={data.candles} />
          <PredictionReview data={data} />
          <CompanyTradeSetups candles={data.candles} />
        </Paper>
      ) : (
        <Text c="dimmed">Market prices, stock trends and outlooks require Markets access.</Text>
      )}

      <CompanyValuation data={data} />

      {/* 7. Fundamentals Section */}
      <section id="fundamentals" aria-label="Company fundamentals">
        <Group justify="space-between" align="baseline" wrap="wrap" gap="sm">
          <Title order={2} size="h3">
            Fundamentals
          </Title>
        </Group>
        <Text c="dimmed" my="sm">
          {data.fundamentals_source
            ? `Saved ${data.fundamentals_as_of ? savedTime(data.fundamentals_as_of) + " IST" : "at an unknown time"}`
            : "No saved fundamentals."}{" "}
          Financial-statement units and reporting periods are supplied by the source. Sector market
          cap is not the company's market cap.
        </Text>
        <Fundamentals data={data} />
      </section>

      {/* 8. Company News Section */}
      {hasNews && (
        <section id="company-news" aria-label="Company news">
          <Group justify="space-between" align="baseline" wrap="wrap" gap="sm" mb="xs">
            <Title order={2} size="h3">
              Company news
            </Title>
            {data.news.length > 0 && (
              <Group gap="xs">
                <Badge variant="light" color="teal" size="sm">
                  {
                    data.news.filter((s) => s.sentiment_score !== null && s.sentiment_score > 0)
                      .length
                  }{" "}
                  Positive
                </Badge>
                <Badge variant="light" color="gray" size="sm">
                  {
                    data.news.filter((s) => s.sentiment_score === null || s.sentiment_score === 0)
                      .length
                  }{" "}
                  Neutral
                </Badge>
                <Badge variant="light" color="red" size="sm">
                  {
                    data.news.filter((s) => s.sentiment_score !== null && s.sentiment_score < 0)
                      .length
                  }{" "}
                  Negative
                </Badge>
              </Group>
            )}
          </Group>
          <Text size="sm" c="dimmed" mb="md">
            Latest 30 linked articles. Sentiment ranges from -1 (negative) to +1 (positive);
            relevance ranges from 0 to 1. Sentiment is not a prediction.
          </Text>
          {data.news.length ? (
            <DataTable
              data={data.news}
              label="Company news"
              columns={companyNewsColumns}
              initialSort={[{ id: "published_at", desc: true }]}
              filters={[
                {
                  label: "Source",
                  value: (story) => story.source,
                  options: [
                    ...new Set(data.news.map((story) => story.source).filter(Boolean)),
                  ].sort(),
                },
                {
                  label: "Sentiment",
                  value: (story) =>
                    story.sentiment_score === null
                      ? "Not scored"
                      : story.sentiment_score > 0
                        ? "Positive"
                        : story.sentiment_score < 0
                          ? "Negative"
                          : "Neutral",
                  options: ["Positive", "Neutral", "Negative", "Not scored"],
                },
              ]}
            />
          ) : (
            <Text c="dimmed">No linked news saved.</Text>
          )}
        </section>
      )}

      {/* 9. IPO Scores Section */}
      {hasIpos && (
        <section id="company-ipos" aria-label="IPO scores">
          <Title order={2} size="h3" mb="md">
            IPO scores
          </Title>
          <Stack gap="md">
            {data.ipos.length ? (
              data.ipos.map((ipo) => (
                <Paper key={ipo.id} p="md" withBorder className="company-ipo-card">
                  <Group justify="space-between" align="center" wrap="wrap" gap="sm" mb="xs">
                    <Link
                      to="/ipos/$id/"
                      params={{ id: String(ipo.id) }}
                      className="company-ipo-link"
                    >
                      <Text fw={650} size="md">
                        {ipo.name}
                      </Text>
                    </Link>
                    <Group gap="xs">
                      {ipo.verdict && (
                        <Badge
                          variant="light"
                          color={ipo.verdict.toLowerCase().includes("avoid") ? "red" : "teal"}
                        >
                          {ipo.verdict}
                        </Badge>
                      )}
                      {ipo.score !== null && (
                        <Badge variant="filled" color="violet">
                          Score: {score(ipo.score)}
                        </Badge>
                      )}
                    </Group>
                  </Group>
                  <Text size="sm" c="dimmed" mb="sm">
                    Score (-1 to +1): {score(ipo.score)} | {ipo.verdict || "No verdict"}
                  </Text>
                  <Accordion variant="separated">
                    <Accordion.Item value="inputs">
                      <Accordion.Control>All IPO scoring inputs</Accordion.Control>
                      <Accordion.Panel>
                        <SavedFacts value={ipo.score_inputs} />
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                </Paper>
              ))
            ) : (
              <Text c="dimmed">No linked IPO scores.</Text>
            )}
          </Stack>
        </section>
      )}
    </Stack>
  );
}
