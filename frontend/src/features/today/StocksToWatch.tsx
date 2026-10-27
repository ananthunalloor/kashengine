import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { AppLink } from "../../shared/ui/AppLink";
import type { StocksWatch, StockWatchItem } from "../../shared/api/generated/types.gen";
import { sourceLink } from "../../shared/ui/sourceLink";
import { formatReportDate } from "../../shared/ui/formatReportDate";

const time = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "short",
});
const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const biasLabels = {
  bullish: {
    label: "Bullish news bias",
    color: "teal",
    explanation: "News leans positive; upward pressure is possible, not assured.",
  },
  bearish: {
    label: "Bearish news bias",
    color: "red",
    explanation: "News leans negative; downward pressure is possible, not assured.",
  },
  mixed: {
    label: "Mixed news",
    color: "orange",
    explanation: "Positive and negative stories conflict. No clear directional view.",
  },
  neutral: {
    label: "No clear news edge",
    color: "gray",
    explanation: "The scored news does not support a clear direction.",
  },
} as const;

function WatchCompany({ item }: { item: StockWatchItem }) {
  const bias = biasLabels[item.bias];
  return (
    <Paper withBorder p="md" component="article" aria-label={`${item.symbol} news watch`}>
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <div>
            <Anchor component={AppLink} href={`/companies/${item.id}/`} fw={600}>
              {item.name}
            </Anchor>
            <Text size="xs" c="dimmed">
              {item.symbol}
              {item.sector ? ` · ${item.sector}` : ""}
            </Text>
          </div>
          <Badge variant="light" color={bias.color}>
            {bias.label}
          </Badge>
        </Group>
        <Text size="sm">{bias.explanation}</Text>
        <Group gap="xs">
          <Badge variant="light" color="gray">
            {item.articles} {item.articles === 1 ? "article" : "articles"}
          </Badge>
          <Badge variant="light" color="gray">
            {item.sources} {item.sources === 1 ? "source" : "sources"}
          </Badge>
          {item.articles === 1 && (
            <Badge variant="outline" color="orange">
              Single-article evidence
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          Latest news{" "}
          <time dateTime={item.latest_news_at}>
            {time.format(new Date(item.latest_news_at))} IST
          </time>
          . {item.positive} positive · {item.negative} negative; remaining stories neutral.
        </Text>
        <Stack gap="xs">
          {item.stories.map((story) => {
            const href = sourceLink(story.url);
            return (
              <div key={story.url}>
                {href ? (
                  <Anchor size="sm" href={href} target="_blank" rel="noopener noreferrer">
                    {story.title}
                    <span className="sr-only"> (opens in a new tab)</span>
                  </Anchor>
                ) : (
                  <Text size="sm">{story.title}</Text>
                )}
                <Text size="xs" c="dimmed">
                  {story.source} ·{" "}
                  <time dateTime={story.published_at}>
                    {time.format(new Date(story.published_at))} IST
                  </time>
                </Text>
                {story.sentiment_reason && <Text size="sm">{story.sentiment_reason}</Text>}
              </div>
            );
          })}
        </Stack>
        <Text size="xs" c="dimmed">
          News balance {item.score > 0 ? "+" : ""}
          {number.format(item.score)} on -1 to +1. Not a probability or expected price change.
        </Text>
      </Stack>
    </Paper>
  );
}

export function StocksToWatch({ data }: { data: StocksWatch }) {
  const active = data.session_state === "pre_open" || data.session_state === "open";
  return (
    <Stack component="section" gap="md" aria-labelledby="stocks-to-watch">
      <Group justify="space-between" align="center">
        <div>
          <Title order={2} size="h3" id="stocks-to-watch">
            Stocks to watch today
          </Title>
          <Text size="sm" c="dimmed">
            {formatReportDate(data.session_date)} · news-based movement watch
          </Text>
        </div>
        <Badge color={data.session_state === "open" ? "teal" : "gray"} variant="light">
          {data.session_state === "open"
            ? "Session open at snapshot"
            : data.session_state === "pre_open"
              ? "Pre-open snapshot"
              : data.session_state === "ended"
                ? "Session ended"
                : "No session today"}
        </Badge>
      </Group>
      <Text size="sm" c="dimmed">
        Experimental news bias, not a reliable forecast or buy/sell signal. News sentiment describes
        the article, not necessarily its impact on every company it names. Check current prices and
        company announcements before acting.
      </Text>
      {!active ? (
        <Alert
          color="gray"
          title={
            data.session_state === "ended"
              ? "Today's trading session has ended"
              : "Market closed today"
          }
        >
          No today's-movement calls are shown. Next scheduled session:{" "}
          {formatReportDate(data.next_session)}.
        </Alert>
      ) : data.items.length ? (
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
          {data.items.map((item) => (
            <WatchCompany key={item.id} item={item} />
          ))}
        </SimpleGrid>
      ) : (
        <Alert color="gray" title="No news-backed stocks to watch yet">
          No eligible recent, scored company-linked news is saved. No direction is guessed from
          missing data. The watchlist appears as news is ingested, scored and linked to companies.
        </Alert>
      )}
      <Text size="xs" c="dimmed">
        Snapshot <time dateTime={data.as_of}>{time.format(new Date(data.as_of))} IST</time> · not a
        live feed.
        {active && (
          <>
            {" "}
            News window from {time.format(new Date(data.since))} IST. {data.sampled_articles}{" "}
            eligible articles checked{data.truncated ? " · coverage limited to the latest 300" : ""}
            .
          </>
        )}
      </Text>
      <Accordion variant="separated">
        <Accordion.Item value="watch-method">
          <Accordion.Control>Why these stocks? How the news bias works</Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              <Text size="sm">
                Uses the latest 36 hours of saved, timestamped, scored news linked to known
                companies. Only valid sentiment (-1 to +1) and market relevance of at least 0.5 are
                used. Future, undated and unscored news are excluded.
              </Text>
              <Text size="sm">
                News balance is the relevance-weighted average sentiment. Above +0.15 is bullish;
                below -0.15 is bearish; otherwise neutral. If individual positive and negative
                stories both cross these thresholds, the view is mixed regardless of the average.
              </Text>
              <Text size="sm">
                Up to eight companies are ranked by average absolute sentiment x relevance, then
                latest news time. Up to three headlines per company are shown; mixed views include
                both positive and negative evidence. This ranks news attention, not expected returns
                or confidence. Multiple outlets may repeat the same event.
              </Text>
              <Text size="sm">
                The calendar respects saved holidays and special sessions. No calls are shown on
                closed days or after session close. This snapshot is calculated from saved news when
                the dashboard loads, is not an archived prediction, and has not been backtested.
                Prices may already reflect the news; sentiment can be wrong. No price target,
                expected percentage move or accuracy claim is inferred.
              </Text>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}
