import {
  Accordion,
  Alert,
  Anchor,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import type { CompanyBar, CompanyDetail, CompanyPrice } from "../../shared/api/generated/types.gen";
import { SavedFacts } from "../../shared/ui/SavedFacts";
import { sourceLink } from "../../shared/ui/sourceLink";
import { usePageTitle } from "../../shared/ui/usePageTitle";

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
    <Stack gap="sm">
      <Title order={3}>INR {number.format(quote.price)}</Title>
      <Text>
        Change from previous close:{" "}
        {quote.change_pct === null ? "Not available" : `${number.format(quote.change_pct)}%`}
      </Text>
      <Text>
        Previous close:{" "}
        {quote.previous_close === null
          ? "Not available"
          : `INR ${number.format(quote.previous_close)}`}
      </Text>
      <Text>
        Volume:{" "}
        {quote.volume === null ? "Not supplied by LTPC stream" : number.format(quote.volume)}
      </Text>
      <QuoteFreshness quote={quote} />
    </Stack>
  );
}

function PriceTrend({ candles }: { candles: CompanyBar[] }) {
  if (!candles.length) return <Text c="dimmed">No saved daily price history.</Text>;
  const closes = candles.map((bar) => bar.close);
  const min = Math.min(...closes),
    max = Math.max(...closes);
  const points = closes
    .map(
      (close, index) =>
        `${20 + (index * 560) / Math.max(1, closes.length - 1)},${140 - ((close - min) * 120) / (max - min || 1)}`,
    )
    .join(" ");
  return (
    <Stack gap="md">
      <Text c="dimmed">
        Completed daily closes in INR. Unadjusted prices: splits and dividends can distort momentum.
      </Text>
      <svg
        viewBox="0 0 600 160"
        role="img"
        aria-label={`Saved closing prices from ${candles[0].day} to ${candles.at(-1)?.day}; low ${min}, high ${max} INR`}
      >
        <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <Accordion variant="separated">
        <Accordion.Item value="history">
          <Accordion.Control>Daily OHLCV history ({candles.length} sessions)</Accordion.Control>
          <Accordion.Panel>
            <Table.ScrollContainer minWidth={550}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    {["Day", "Open", "High", "Low", "Close", "Volume"].map((heading) => (
                      <Table.Th key={heading}>{heading}</Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {[...candles].reverse().map((bar) => (
                    <Table.Tr key={bar.day}>
                      <Table.Td>{bar.day}</Table.Td>
                      {[bar.open, bar.high, bar.low, bar.close, bar.volume].map((value, index) => (
                        <Table.Td key={index}>{number.format(value)}</Table.Td>
                      ))}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

export function CompanyView({ data }: { data: CompanyDetail }) {
  usePageTitle(data.company.name);
  const outlook = data.outlook;
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
        <Accordion variant="separated" multiple>
          {Object.entries(data.fundamentals).map(([key, value]) => (
            <Accordion.Item key={key} value={key}>
              <Accordion.Control>{key.replaceAll("-", " ").replaceAll("_", " ")}</Accordion.Control>
              <Accordion.Panel>
                <SavedFacts value={value} />
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      </section>
      {data.markets_available ? (
        <>
          <Paper p="lg" withBorder>
            <Title order={2} size="h3" mb="md">
              Saved market price
            </Title>
            <PriceSummary quote={data.quote} />
          </Paper>
          <section>
            <Title order={2} size="h3" mb="md">
              Stock trend
            </Title>
            <PriceTrend candles={data.candles} />
          </section>
          <Paper p="lg" withBorder>
            <Title order={2} size="h3">
              Predicted future trend
            </Title>
            <Alert color="orange" my="md" title="Experimental outlook">
              Not financial advice. Not a price target or a measured probability. This rule has not
              been backtested.
            </Alert>
            {outlook ? (
              <Stack gap="md">
                <Text>
                  Saved outlook for {outlook.target_date}: <strong>{outlook.direction}</strong>.
                  Created {savedTime(outlook.created_at)} IST. Historical targets are not current
                  forecasts.
                </Text>
                <SimpleGrid cols={{ base: 1, sm: 3 }}>
                  <Text>Combined score: {score(outlook.score)}</Text>
                  <Text>Momentum score: {score(outlook.momentum_score)}</Text>
                  <Text>News score: {score(outlook.news_score)}</Text>
                </SimpleGrid>
                <Text c="dimmed">
                  Scores run from -1 (down/negative) to +1 (up/positive). Momentum is the 20-session
                  return divided by 10%, capped at +/-1. With news: 70% momentum, 30%
                  relevance-weighted sentiment. Without news: momentum only. Scores within +/-0.15
                  are flat.
                </Text>
                <Accordion>
                  <Accordion.Item value="evidence">
                    <Accordion.Control>All outlook inputs and scores</Accordion.Control>
                    <Accordion.Panel>
                      <SavedFacts value={outlook.inputs} />
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              </Stack>
            ) : (
              <Text c="dimmed">
                {data.news_available
                  ? "No saved outlook. At least 21 recent completed daily bars are required."
                  : "The outlook requires access to News as well as Markets."}
              </Text>
            )}
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
