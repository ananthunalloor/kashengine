import { Badge, Group, Paper, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import { useEffect, useState } from "react";
import { LuArrowDownRight, LuArrowUpRight, LuRadio } from "react-icons/lu";

import type { LiveConnection, LiveMarket, LiveQuote, MarketStatus } from "../api/liveQuotes";

const price = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const quantity = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const clock = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  timeStyle: "medium",
});
const dayClock = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "medium",
});

/** A tick older than this is shown as delayed, not live. */
export const LIVE_STALE_MS = 60_000;

const connectionLabels: Record<LiveConnection, { label: string; color: string }> = {
  connecting: { label: "Connecting", color: "gray" },
  live: { label: "Live", color: "teal" },
  reconnecting: { label: "Reconnecting", color: "orange" },
  "signed-out": { label: "Signed out", color: "red" },
  unavailable: { label: "Live data unavailable", color: "gray" },
  unsupported: { label: "Not supported by this browser", color: "gray" },
};

const segmentLabels: Record<string, string> = {
  PRE_OPEN_START: "Pre-open",
  PRE_OPEN_END: "Pre-open ended",
  NORMAL_OPEN: "Market open",
  NORMAL_CLOSE: "Market closed",
  CLOSING_START: "Closing session",
  CLOSING_END: "Market closed",
};

export function marketStatusLabel(status: MarketStatus | null) {
  const state = status?.segments.NSE_EQ ?? status?.segments.NSE_INDEX;
  return state ? (segmentLabels[state] ?? state.replaceAll("_", " ").toLowerCase()) : null;
}

function useNow(intervalMs = 5_000) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

export function isFresh(quote: LiveQuote, now: number) {
  return now - Date.parse(quote.as_of) <= LIVE_STALE_MS;
}

export function LiveBadge({ connection }: { connection: LiveConnection }) {
  const { label, color } = connectionLabels[connection];
  return (
    <Badge
      variant="light"
      color={color}
      leftSection={<LuRadio aria-hidden="true" />}
      aria-label={`Live data: ${label}`}
    >
      {label}
    </Badge>
  );
}

export function Change({ quote, size = "sm" }: { quote: LiveQuote; size?: "xs" | "sm" | "md" }) {
  if (quote.change === null || quote.change_pct === null)
    return (
      <Text size={size} c="dimmed" component="span">
        Change not available
      </Text>
    );
  const up = quote.change >= 0;
  const Icon = up ? LuArrowUpRight : LuArrowDownRight;
  return (
    <Text size={size} fw={600} c={up ? "teal" : "red"} component="span" className="live-change">
      <Icon aria-hidden="true" /> {up ? "+" : ""}
      {price.format(quote.change)} ({up ? "+" : ""}
      {price.format(quote.change_pct)}%)
    </Text>
  );
}

function TickTime({ quote, now }: { quote: LiveQuote; now: number }) {
  const fresh = isFresh(quote, now);
  return (
    <Group gap={6} align="center" wrap="nowrap">
      <span
        className={`company-freshness-dot ${fresh ? "is-live" : "is-stale"}`}
        aria-hidden="true"
      />
      <Text size="xs" c="dimmed">
        {fresh ? "Last trade " : "Last trade (delayed) "}
        <time dateTime={quote.as_of}>{clock.format(new Date(quote.as_of))} IST</time>
      </Text>
    </Group>
  );
}

function emptyMessage(connection: LiveConnection) {
  if (connection === "connecting") return "Connecting to the live feed…";
  if (connection === "reconnecting") return "Reconnecting to the live feed…";
  if (connection === "unsupported") return "This browser does not support live updates.";
  if (connection === "signed-out") return "Sign in again to see live prices.";
  return "No live ticks yet. The Upstox stream worker must be running with a valid token.";
}

export function LiveIndices({ live }: { live: LiveMarket }) {
  const now = useNow();
  const status = marketStatusLabel(live.status);
  return (
    <section aria-labelledby="live-market" className="live-market">
      <Group justify="space-between" align="center" mb="sm" gap="sm" wrap="wrap">
        <div>
          <Title order={2} size="h3" id="live-market">
            Live market
          </Title>
          <Text size="sm" c="dimmed">
            Index levels streamed from Upstox, about once a second.
          </Text>
        </div>
        <Group gap="xs">
          {status && (
            <Badge variant="outline" color={status === "Market open" ? "teal" : "gray"}>
              {status}
            </Badge>
          )}
          <LiveBadge connection={live.connection} />
        </Group>
      </Group>
      {live.indices.length ? (
        <SimpleGrid cols={{ base: 1, xs: 2, md: Math.min(live.indices.length, 4) }} spacing="sm">
          {live.indices.map((quote) => (
            <Paper
              key={quote.key}
              withBorder
              p="md"
              className="company-stat-card live-index"
              component="article"
              aria-label={`${quote.name} live`}
            >
              <Text size="xs" c="dimmed" fw={600} tt="uppercase">
                {quote.name}
              </Text>
              <Title order={3} className="live-price">
                {price.format(quote.ltp)}
              </Title>
              <Change quote={quote} />
              {quote.low !== null && quote.high !== null && (
                <Text size="xs" c="dimmed">
                  Day range {price.format(quote.low)} – {price.format(quote.high)}
                </Text>
              )}
              <TickTime quote={quote} now={now} />
            </Paper>
          ))}
        </SimpleGrid>
      ) : (
        <Text c="dimmed" size="sm">
          {emptyMessage(live.connection)}
        </Text>
      )}
    </section>
  );
}

export function LivePrice({ quote }: { quote: LiveQuote | undefined }) {
  const now = useNow();
  if (!quote) return null;
  return (
    <Group gap="xs" align="baseline" className="live-inline-price" wrap="wrap">
      <Text fw={700}>INR {price.format(quote.ltp)}</Text>
      <Change quote={quote} size="xs" />
      <Text size="xs" c="dimmed">
        {isFresh(quote, now) ? "live" : "delayed"} ·{" "}
        <time dateTime={quote.as_of}>{clock.format(new Date(quote.as_of))}</time>
      </Text>
    </Group>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="company-quote-metric">
      <Text size="xs" c="dimmed" fw={600} tt="uppercase">
        {label}
      </Text>
      <Text fw={600}>{value}</Text>
    </div>
  );
}

const rupees = (value: number | null) => (value === null ? "–" : `INR ${price.format(value)}`);
const count = (value: number | null) => (value === null ? "–" : quantity.format(value));

export function LiveCompanyQuote({
  quote,
  connection,
  status,
}: {
  quote: LiveQuote;
  connection: LiveConnection;
  status: MarketStatus | null;
}) {
  const now = useNow();
  const buy = quote.total_buy_qty ?? 0;
  const sell = quote.total_sell_qty ?? 0;
  const buyShare = buy + sell > 0 ? (buy / (buy + sell)) * 100 : null;
  const session = marketStatusLabel(status);
  return (
    <Stack gap="xs" className="company-quote-summary live-company-quote" aria-label="Live quote">
      <Group justify="space-between" align="center" gap="xs">
        <Group gap="xs">
          <LiveBadge connection={connection} />
          {session && (
            <Badge variant="outline" color={session === "Market open" ? "teal" : "gray"}>
              {session}
            </Badge>
          )}
        </Group>
        <TickTime quote={quote} now={now} />
      </Group>
      <Group align="baseline" gap="sm">
        <Title order={3} className="live-price">
          INR {price.format(quote.ltp)}
        </Title>
        <Change quote={quote} size="md" />
      </Group>
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
        <Metric label="Open" value={rupees(quote.open)} />
        <Metric label="High" value={rupees(quote.high)} />
        <Metric label="Low" value={rupees(quote.low)} />
        <Metric label="Previous close" value={rupees(quote.previous_close)} />
        <Metric label="Volume" value={count(quote.volume)} />
        <Metric label="Average price" value={rupees(quote.average_price)} />
        <Metric label="Total buy qty" value={count(quote.total_buy_qty)} />
        <Metric label="Total sell qty" value={count(quote.total_sell_qty)} />
      </SimpleGrid>
      {buyShare !== null && (
        <div>
          <div
            className="live-pressure"
            role="img"
            aria-label={`Buy orders ${price.format(buyShare)}% of pending quantity`}
          >
            <span style={{ width: `${buyShare}%` }} />
          </div>
          <Group justify="space-between">
            <Text size="xs" c="teal">
              Buy {price.format(buyShare)}%
            </Text>
            <Text size="xs" c="red">
              Sell {price.format(100 - buyShare)}%
            </Text>
          </Group>
        </div>
      )}
      {quote.depth.length > 0 && (
        <Table.ScrollContainer minWidth={320}>
          <Table striped withTableBorder fz="xs" aria-label="Market depth (top 5)">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Bid qty</Table.Th>
                <Table.Th>Bid</Table.Th>
                <Table.Th>Ask</Table.Th>
                <Table.Th>Ask qty</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {quote.depth.map((level, index) => (
                <Table.Tr key={index}>
                  <Table.Td>{quantity.format(level.bid_qty)}</Table.Td>
                  <Table.Td c="teal">
                    {level.bid_price ? price.format(level.bid_price) : "–"}
                  </Table.Td>
                  <Table.Td c="red">
                    {level.ask_price ? price.format(level.ask_price) : "–"}
                  </Table.Td>
                  <Table.Td>{quantity.format(level.ask_qty)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Text size="xs" c="dimmed">
        Streamed from Upstox · received {dayClock.format(new Date(quote.as_of))} IST. Not investment
        advice.
      </Text>
    </Stack>
  );
}
