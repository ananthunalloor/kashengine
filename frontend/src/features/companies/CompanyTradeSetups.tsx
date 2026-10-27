import { Alert, Badge, Stack, Table, Text, Title } from "@mantine/core";
import type { CompanyBar } from "../../shared/api/generated/types.gen";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function tradeEvidence(candles: CompanyBar[]) {
  if (candles.length < 21) return null;
  const recent = candles.slice(-21);
  if (
    recent.some(
      (bar, index) =>
        ![bar.open, bar.high, bar.low, bar.close, bar.volume].every(Number.isFinite) ||
        bar.low <= 0 ||
        bar.high < Math.max(bar.open, bar.close, bar.low) ||
        bar.low > Math.min(bar.open, bar.close) ||
        bar.volume < 0 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(bar.day) ||
        !Number.isFinite(Date.parse(`${bar.day}T00:00:00Z`)) ||
        new Date(`${bar.day}T00:00:00Z`).toISOString().slice(0, 10) !== bar.day ||
        (index > 0 && bar.day <= recent[index - 1].day),
    )
  )
    return null;
  const last = recent.at(-1)!;
  const previous = recent.slice(0, -1);
  const support = Math.min(...previous.map((bar) => bar.low));
  const resistance = Math.max(...previous.map((bar) => bar.high));
  if (resistance <= support) return null;
  const sma20 = recent.slice(-20).reduce((sum, bar) => sum + bar.close, 0) / 20;
  const history50 = candles.slice(-50);
  const sma50 =
    candles.length >= 50 && history50.every((bar) => Number.isFinite(bar.close) && bar.close > 0)
      ? history50.reduce((sum, bar) => sum + bar.close, 0) / 50
      : null;
  const rising = last.close > sma20 && last.close > previous[0].close;
  const averageVolume = previous.reduce((sum, bar) => sum + bar.volume, 0) / 20;
  return {
    last,
    support,
    resistance,
    sma20,
    sma50,
    rising,
    volumeConfirmed: averageVolume > 0 && last.volume > averageVolume,
    risk: resistance - support,
  };
}

export function CompanyTradeSetups({ candles }: { candles: CompanyBar[] }) {
  const evidence = tradeEvidence(candles);
  const stale = evidence
    ? Date.now() - Date.parse(`${evidence.last.day}T15:30:00+05:30`) > 7 * 86_400_000
    : false;
  const watch = evidence && !stale && evidence.rising;
  return (
    <Stack gap="sm" mt="lg">
      <Title order={3} size="h4">
        Trade setup watchlist
      </Title>
      <Text size="sm" c="dimmed">
        Educational, rule-based scenarios from saved daily candles, not a buy/sell recommendation, a
        forecast or personalized advice. Confirm current prices, liquidity and corporate actions
        before considering any order. These rules have not been backtested.
      </Text>
      {!evidence ? (
        <Alert color="gray" title="Wait / insufficient data">
          At least 21 valid daily OHLCV sessions and a non-zero price range are needed for a setup.
          No entry, stop or target is inferred from missing data.
        </Alert>
      ) : (
        <>
          {stale && (
            <Alert color="orange" title="Wait / stale history">
              Latest candle is more than 7 calendar days old. Refresh saved history before
              evaluating any setup.
            </Alert>
          )}
          <Text size="sm">
            Evidence as of {evidence.last.day}: close INR {number.format(evidence.last.close)}, SMA
            20 INR {number.format(evidence.sma20)}
            {evidence.sma50 !== null && `, SMA 50 INR ${number.format(evidence.sma50)}`}. Prior
            20-session low/high: INR {number.format(evidence.support)} /{" "}
            {number.format(evidence.resistance)}.{" "}
            {evidence.volumeConfirmed
              ? "Latest volume exceeds"
              : "Latest volume does not confirm above"}{" "}
            the prior 20-session average.
          </Text>
          <Table.ScrollContainer minWidth={640}>
            <Table withTableBorder withRowBorders>
              <Table.Caption>Conditional trading styles for this company</Table.Caption>
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
                    <Badge color={watch ? "teal" : "gray"}>
                      {watch ? "Watch for confirmation" : "Wait / no long setup"}
                    </Badge>
                    <Text size="sm" mt="xs">
                      {evidence.rising
                        ? "Close is above SMA 20 with positive 20-session momentum."
                        : "Trend and momentum do not both support a long setup."}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    Watch only after a completed daily close above INR{" "}
                    {number.format(evidence.resistance)} with above-average volume. If already
                    above, do not chase; reassess a retest. Illustrative invalidation: below INR{" "}
                    {number.format(evidence.support)}. At an assumed entry of INR{" "}
                    {number.format(evidence.resistance)}, risk is INR {number.format(evidence.risk)}{" "}
                    per share ({number.format((evidence.risk / evidence.resistance) * 100)}%), and a
                    2R scenario is INR {number.format(evidence.resistance + 2 * evidence.risk)}.
                  </Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Positional long · weeks to months</Table.Td>
                  <Table.Td>
                    <Badge color="gray">
                      {stale
                        ? "Wait / stale history"
                        : evidence.sma50 === null
                          ? "Need 50 sessions"
                          : watch && evidence.sma20 > evidence.sma50
                            ? "Trend-aligned watch"
                            : "Wait / trend not aligned"}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    Require close &gt; SMA 20 &gt; SMA 50, then reassess entry after a confirmed
                    breakout or supported pullback. Review earnings, valuation, cash flow and debt;
                    daily technicals alone do not establish investment quality.
                  </Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>Intraday / short selling</Table.Td>
                  <Table.Td>
                    <Badge color="gray">Not assessable</Badge>
                  </Table.Td>
                  <Table.Td>
                    Daily saved data cannot establish intraday entries, spreads, execution liquidity
                    or short eligibility. A weak trend is not a short recommendation; avoid
                    unsupported long entries.
                  </Table.Td>
                </Table.Tr>
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Text size="xs" c="dimmed">
            2R is arithmetic, not a predicted target or guaranteed reward. Levels use the prior 20
            sessions, excluding the latest candle. Actual entry changes risk/reward; gaps, fees and
            slippage can exceed a stop. Size positions to a predefined loss budget; wait if the stop
            distance is unsuitable. Even recent daily history is not live.
          </Text>
        </>
      )}
    </Stack>
  );
}
