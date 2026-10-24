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
import { LuInfo } from "react-icons/lu";
import { useEffect, useState } from "react";

import type { CompanyBar, CompanyDetail, CompanyPrice } from "../../shared/api/generated/types.gen";
import { DataTable } from "../../shared/ui/DataTable";
import type { TableColumn } from "../../shared/ui/DataTable";
import { SavedFacts } from "../../shared/ui/SavedFacts";
import { sourceLink } from "../../shared/ui/sourceLink";
import { CandlestickTrendChart } from "../../shared/ui/TanStackCharts";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const projectionWindow = 20;
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

export function projectClosingPrices(candles: CompanyBar[]): { label: string; value: number }[] {
  if (candles.length < projectionWindow) return [];
  const closes = candles.slice(-projectionWindow).map((bar) => bar.close);
  const meanX = (closes.length - 1) / 2;
  const meanY = closes.reduce((total, close) => total + close, 0) / closes.length;
  const slope =
    closes.reduce((total, close, index) => total + (index - meanX) * (close - meanY), 0) /
    closes.reduce((total, _, index) => total + (index - meanX) ** 2, 0);
  const last = candles.at(-1)!;

  return [
    { label: last.day, value: last.close },
    ...Array.from({ length: projectionWindow }, (_, index) => ({
      label: `T+${index + 1}`,
      value: last.close + slope * (index + 1),
    })),
  ];
}

export function QuoteFreshness({ quote }: { quote: CompanyPrice }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, []);
  const stale = now - Date.parse(quote.as_of) > (quote.mode === "stream" ? 15_000 : 600_000);
  return (
    <Text size="sm" c={stale ? "dimmed" : undefined}>
      {quote.mode === "stream" ? "Stream observation" : "Scheduled snapshot"}
      {stale ? " - older observation, not live" : ""}
      {" | "}
      <time dateTime={quote.as_of}>{savedTime(quote.as_of)} IST</time>
    </Text>
  );
}

export function PriceSummary({ quote }: { quote: CompanyPrice | null }) {
  if (!quote)
    return (
      <Text c="dimmed">
        No saved quote. Configure the company's Upstox instrument key and run ingestion.
      </Text>
    );
  return (
    <Stack gap="xs" className="company-quote-summary">
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
        <div>
          <Text size="xs" c="dimmed">
            Last price
          </Text>
          <Title order={3}>INR {number.format(quote.price)}</Title>
        </div>
        <div>
          <Text size="xs" c="dimmed">
            Change
          </Text>
          <Text
            fw={600}
            c={quote.change_pct === null ? "dimmed" : quote.change_pct >= 0 ? "teal" : "red"}
          >
            {quote.change_pct === null ? "Not available" : `${number.format(quote.change_pct)}%`}
          </Text>
        </div>
        <div>
          <Text size="xs" c="dimmed">
            Previous close
          </Text>
          <Text fw={600}>
            {quote.previous_close === null
              ? "Not available"
              : `INR ${number.format(quote.previous_close)}`}
          </Text>
        </div>
        <div>
          <Text size="xs" c="dimmed">
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
        candles={candles.slice(-60).map((bar) => ({ ...bar, label: bar.day }))}
        projectionPoints={projectionPoints}
        ariaLabel={`Daily candlestick chart from ${candles.at(-60)?.day ?? candles[0].day} to ${candles.at(-1)?.day}${projection.length ? ", followed by a 20-session history-only linear projection" : ""}; each candle shows open, high, low and close in INR`}
        height={240}
      />
      <Text c="dimmed" size="sm">
        Each candle shows open, high, low and close in INR. The dashed line extends a linear fit of
        the latest 20 closes across 20 future sessions; it is not a price target or financial
        advice, has not been backtested, and splits or dividends can distort it.
      </Text>
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

type FundamentalFact = {
  label: string;
  value: unknown;
  comparison?: unknown;
};

function humanize(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim();
}

function collectFacts(value: unknown, path: string[] = []): FundamentalFact[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => {
      const rowName =
        item && typeof item === "object" && !Array.isArray(item) && typeof item.name === "string"
          ? item.name
          : `Record ${index + 1}`;
      return collectFacts(item, [...path, rowName]);
    });
  }
  if (!value || typeof value !== "object") return [];

  const record = value as Record<string, unknown>;
  if (typeof record.name === "string" && Object.hasOwn(record, "company_value")) {
    return [
      {
        label: record.name,
        value: record.company_value,
        ...(Object.hasOwn(record, "sector_value") ? { comparison: record.sector_value } : {}),
      },
    ];
  }

  return Object.entries(record).flatMap(([key, item]) => {
    if (key === "name" && typeof item === "string") return [];
    const label = [...path, humanize(key)].filter(Boolean).join(" · ");
    if (item === null || ["string", "number", "boolean"].includes(typeof item)) {
      return [{ label, value: item }];
    }
    return collectFacts(item, [...path, humanize(key)]);
  });
}

function significance(label: string, category: string) {
  const coreMetric =
    /valuation|market cap|revenue|profit|earnings|eps|return on|roe|roce|debt|cash flow|margin/i.test(
      label,
    );
  if (coreMetric) return { label: "High significance", color: "teal" };
  if (category === "key ratios") return { label: "Supporting", color: "blue" };
  return { label: "Contextual", color: "gray" };
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
  return `Provider-reported ${humanize(label)}. Check its unit, reporting period and sector context before comparing; significance describes analytical relevance, not whether the value is good or bad.`;
}

function factValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "number") return number.format(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function Fundamentals({ data }: { data: CompanyDetail }) {
  const categories = Object.entries(data.fundamentals)
    .map(([key, value]) => ({ label: humanize(key), facts: collectFacts(value) }))
    .filter((category) => category.facts.length > 0);

  if (!categories.length) return <Text c="dimmed">No saved fundamentals.</Text>;

  return (
    <Stack gap="lg" className="company-fundamentals">
      <Text size="sm" c="dimmed">
        Significance indicates common analytical relevance, not whether a value is favorable. Always
        check source units, reporting periods and sector context.
      </Text>
      {categories.map((category) => (
        <section
          key={category.label}
          aria-label={category.label}
          className="company-fundamental-group"
        >
          <Group justify="space-between" mb="sm" align="baseline">
            <Title order={3} size="h4" tt="capitalize">
              {category.label}
            </Title>
            <Text size="xs" c="dimmed">
              {category.facts.length} metrics
            </Text>
          </Group>
          <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }} spacing="xs">
            {category.facts.map((fact, index) => {
              const rank = significance(fact.label, category.label);
              return (
                <Paper
                  key={`${fact.label}-${index}`}
                  p="sm"
                  withBorder
                  className="company-fact-card"
                >
                  <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
                    <Text size="sm" fw={600} className="company-fact-label">
                      {humanize(fact.label)}
                    </Text>
                    <Tooltip label={factDescription(fact.label)} multiline w={280} withArrow>
                      <ActionIcon
                        variant="subtle"
                        size="sm"
                        aria-label={`About ${humanize(fact.label)}`}
                      >
                        <LuInfo aria-hidden="true" />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                  <Text
                    className={`company-fact-value${typeof fact.value === "string" && fact.value.length > 100 ? " company-fact-value-text" : ""}`}
                  >
                    {factValue(fact.value)}
                  </Text>
                  {fact.comparison !== undefined && (
                    <Text size="xs" c="dimmed">
                      Sector comparison: {factValue(fact.comparison)}
                    </Text>
                  )}
                  <Badge size="sm" variant="light" color={rank.color} mt="sm">
                    {rank.label}
                  </Badge>
                </Paper>
              );
            })}
          </SimpleGrid>
        </section>
      ))}
    </Stack>
  );
}

export function CompanyView({ data }: { data: CompanyDetail }) {
  usePageTitle(data.company.name);
  return (
    <Stack gap="xl">
      <header>
        <Anchor component={Link} to="/companies/">
          Companies
        </Anchor>
        <Title order={1}>{data.company.name}</Title>
        <Text>
          {data.company.symbol} | {data.company.sector || "Sector not available"}
        </Text>
        <Text c="dimmed">{data.instrument_key || "No Upstox instrument mapping configured."}</Text>
      </header>
      {Object.entries(data.errors).map(([section, message]) => (
        <Alert key={section} color="orange" title={`${section} refresh failed`}>
          {message} Previously saved data is retained.
        </Alert>
      ))}
      <Paper p="lg" withBorder>
        <Title order={2} size="h3" mb="md">
          Company summary
        </Title>
        <Text>{data.summary || "No provider business summary has been saved yet."}</Text>
      </Paper>
      <section aria-label="Company fundamentals">
        <Title order={2} size="h3">
          Fundamentals
        </Title>
        <Text c="dimmed" my="sm">
          {data.fundamentals_source
            ? `${data.fundamentals_source} | saved ${data.fundamentals_as_of ? savedTime(data.fundamentals_as_of) + " IST" : "at an unknown time"}`
            : "No saved fundamentals."}{" "}
          Financial-statement units and reporting periods are supplied by the source. Sector market
          cap is not the company's market cap.
        </Text>
        <Fundamentals data={data} />
      </section>
      {data.markets_available ? (
        <>
          <Paper p="md" withBorder className="company-market-panel">
            <Group justify="space-between" align="flex-start" mb="md" gap="md">
              <div>
                <Title order={2} size="h3">
                  Market price &amp; trend
                </Title>
                <Text size="sm" c="dimmed">
                  Daily OHLC candles with a history-only projection.
                </Text>
              </div>
              <PriceSummary quote={data.quote} />
            </Group>
            <PriceTrend candles={data.candles} />
          </Paper>
        </>
      ) : (
        <Text c="dimmed">Market prices, stock trends and outlooks require Markets access.</Text>
      )}
      {data.news_available && (
        <section>
          <Title order={2} size="h3" mb="md">
            Company news and sentiment scores
          </Title>
          <Text size="sm" c="dimmed" mb="md">
            Latest 30 linked articles. Sentiment: -1 to +1; relevance: 0 to 1.
          </Text>
          <Stack gap="md">
            {data.news.length ? (
              data.news.map((story) => {
                const href = sourceLink(story.url);
                return (
                  <Paper p="md" withBorder key={story.url}>
                    {href ? (
                      <Anchor href={href} target="_blank" rel="noopener noreferrer">
                        {story.title}
                      </Anchor>
                    ) : (
                      <Text>{story.title}</Text>
                    )}
                    <Text size="sm" c="dimmed">
                      {story.source} |{" "}
                      {story.published_at
                        ? savedTime(story.published_at) + " IST"
                        : "Publication time unavailable"}
                    </Text>
                    <Group>
                      <Text>Sentiment: {score(story.sentiment_score)}</Text>
                      <Text>Relevance: {score(story.relevance)}</Text>
                    </Group>
                    <Text>{story.sentiment_reason || "No scoring reason saved."}</Text>
                  </Paper>
                );
              })
            ) : (
              <Text c="dimmed">No linked news saved.</Text>
            )}
          </Stack>
        </section>
      )}
      {data.ipos_available && (
        <section>
          <Title order={2} size="h3" mb="md">
            IPO scores
          </Title>
          <Stack>
            {data.ipos.length ? (
              data.ipos.map((ipo) => (
                <Paper key={ipo.id} p="md" withBorder>
                  <Link to="/ipos/$id/" params={{ id: String(ipo.id) }}>
                    {ipo.name}
                  </Link>
                  <Text>
                    Score (-1 to +1): {score(ipo.score)} | {ipo.verdict || "No verdict"}
                  </Text>
                  <Accordion>
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
