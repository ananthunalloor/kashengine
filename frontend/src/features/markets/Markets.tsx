import { Anchor, Stack, Text, Title } from "@mantine/core";
import { LuChartNoAxesCombined } from "react-icons/lu";
import { Link } from "@tanstack/react-router";

import type { Markets as MarketsData } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { DataTable } from "../../shared/ui/DataTable";
import { displayNumber } from "../../shared/ui/displayNumber";
import { MetricValue, StrengthLegend } from "../../shared/ui/MetricValue";
import { MarketCloses, MarketDate } from "./MarketCloses";

function Direction({ value }: { value: string }) {
  return value ? (
    <span className="report-outlook" data-tone={value}>
      {value === "up" ? "Up" : value === "down" ? "Down" : "Flat"}
    </span>
  ) : (
    <span>Not available</span>
  );
}

export function Markets({ data, isStaff }: { data: MarketsData; isStaff: boolean }) {
  usePageTitle("Markets");
  const { stats, quotes, history } = data;
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuChartNoAxesCombined aria-hidden="true" />
          The market, in context
        </Text>
        <Title order={1}>Markets</Title>
        <Text c="dimmed" mt="sm">
          Saved closes and the track record of our daily outlook.
        </Text>
        <Link to="/markets/live/" search={{ q: "", page: 1 }}>
          View company market data
        </Link>
        {" · "}
        <Link
          to="/markets/instruments/"
          search={{
            q: "",
            page: 1,
            exchange: "",
            segment: "",
            instrument_type: "",
          }}
        >
          NSE &amp; BSE instruments
        </Link>
        <Anchor href="/markets/" size="sm">
          Compare with the original Markets page
        </Anchor>
      </header>

      <section className="news-card" aria-labelledby="market-record">
        <Title order={2} id="market-record" size="h3">
          Track record
        </Title>
        {stats.total ? (
          <>
            <Text mt="sm">
              The prediction was right on {stats.correct} of {stats.total} days ({stats.accuracy}).
              If we guessed the most common result ({stats.baseline_direction}) every day, we would
              be right {stats.baseline_accuracy}.
            </Text>
            {!stats.enough_results && (
              <Text c="dimmed" size="sm" mt="sm">
                There are too few results to trust these numbers. About 30 are the least.
              </Text>
            )}
            <dl className="market-summary">
              <div>
                <dt>Strong signals</dt>
                <dd>
                  {stats.high_confidence.correct} of {stats.high_confidence.n} right
                </dd>
              </div>
              <div>
                <dt>Last {stats.recent.n} days</dt>
                <dd>{stats.recent.correct} right</dd>
              </div>
              <div>
                <dt>Waiting for the result</dt>
                <dd>{stats.pending}</dd>
              </div>
            </dl>
          </>
        ) : (
          <Text c="dimmed" mt="sm">
            There are no results yet. A prediction gets its result after the market closes on its
            day. {stats.pending} {stats.pending === 1 ? "waits" : "wait"} for a result.
          </Text>
        )}
      </section>

      <section aria-labelledby="market-quotes">
        <Title order={2} id="market-quotes" size="h3" mb="md">
          Last close
        </Title>
        {quotes.length ? (
          <MarketCloses quotes={quotes} />
        ) : (
          <Text c="dimmed">No saved closes yet.</Text>
        )}
      </section>

      <section aria-labelledby="market-history">
        <Title order={2} id="market-history" size="h3">
          Predictions
        </Title>
        <Text c="dimmed" size="sm" mt="sm" mb="md">
          The latest 30 predictions. Strength runs from 1.0/10 (weakest) to 10.0/10 (strongest). It
          is not a probability of being right. <StrengthLegend />
        </Text>
        {history.length ? (
          <DataTable
            data={history}
            label="Predictions (latest 30)"
            initialSort={[{ id: "date", desc: true }]}
            filters={[
              {
                label: "Result",
                value: (row) => row.result,
                options: ["Right", "Wrong", "No session", "Waiting"],
              },
              {
                label: "Direction",
                value: (row) => row.direction,
                options: ["up", "down", "flat"],
              },
            ]}
            columns={[
              {
                id: "date",
                label: "Day",
                value: (row) => row.date,
                render: (row) => <MarketDate day={row.date} />,
              },
              {
                id: "direction",
                label: "We said",
                value: (row) => row.direction,
                render: (row) => <Direction value={row.direction} />,
              },
              {
                id: "strength",
                label: "Strength",
                value: (row) => displayNumber(row.strength),
                render: (row) => <MetricValue kind="strength" value={row.strength} />,
              },
              {
                id: "actual_direction",
                label: "It was",
                value: (row) => row.actual_direction,
                render: (row) => <Direction value={row.actual_direction} />,
              },
              {
                id: "change",
                label: "Change",
                value: (row) => displayNumber(row.change),
                render: (row) => <MetricValue kind="change" value={row.change} />,
              },
              {
                id: "result",
                label: "Result",
                value: (row) => row.result,
                render: (row) => (
                  <span
                    className="report-status"
                    data-tone={
                      row.result === "Right"
                        ? "sent"
                        : row.result === "Wrong"
                          ? "failed"
                          : undefined
                    }
                  >
                    {row.result}
                  </span>
                ),
              },
            ]}
          />
        ) : (
          <Text c="dimmed">
            No prediction yet.
            {isStaff && (
              <>
                {" "}
                Admins: start "Make the prediction" on the <Anchor href="/ops/jobs/">
                  Jobs
                </Anchor>{" "}
                page.
              </>
            )}
          </Text>
        )}
      </section>
    </Stack>
  );
}
