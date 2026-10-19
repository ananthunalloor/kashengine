import { Anchor, Stack, Text, Title } from "@mantine/core";

import type { Markets as MarketsData } from "../../shared/api/generated/types.gen";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const tradingDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
});

function MarketDate({ day }: { day: string }) {
  return <time dateTime={day}>{tradingDate.format(new Date(`${day}T00:00:00+05:30`))}</time>;
}

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
          The market, in context
        </Text>
        <Title order={1} tabIndex={-1}>
          Markets
        </Title>
        <Text c="dimmed" mt="sm">
          Saved closes and the track record of our daily outlook.
        </Text>
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
          <ul className="market-quotes">
            {quotes.map((quote, index) => (
              <li className="news-card" key={index}>
                <Title order={3} size="h4">
                  {quote.name}
                </Title>
                <dl className="market-summary">
                  <div>
                    <dt>Close</dt>
                    <dd>{quote.close}</dd>
                  </div>
                  <div>
                    <dt>Change</dt>
                    <dd>{quote.change}</dd>
                  </div>
                  <div>
                    <dt>Trading day</dt>
                    <dd>
                      <MarketDate day={quote.day} />
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
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
          is not a probability of being right.
        </Text>
        {history.length ? (
          <ul className="news-list">
            {history.map((prediction) => (
              <li className="news-card" key={prediction.date}>
                <div className="news-card-heading">
                  <Title order={3} size="h4">
                    <MarketDate day={prediction.date} />
                  </Title>
                  <span
                    className="report-status"
                    data-tone={
                      prediction.result === "Right"
                        ? "sent"
                        : prediction.result === "Wrong"
                          ? "failed"
                          : undefined
                    }
                  >
                    {prediction.result}
                  </span>
                </div>
                <dl className="market-summary market-prediction">
                  <div>
                    <dt>We said</dt>
                    <dd>
                      <Direction value={prediction.direction} />
                    </dd>
                  </div>
                  <div>
                    <dt>Strength</dt>
                    <dd>{prediction.strength}</dd>
                  </div>
                  <div>
                    <dt>It was</dt>
                    <dd>
                      <Direction value={prediction.actual_direction} />
                    </dd>
                  </div>
                  <div>
                    <dt>Change</dt>
                    <dd>{prediction.change}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
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
