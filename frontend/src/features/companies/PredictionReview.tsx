import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Group,
  NativeSelect,
  Paper,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useState } from "react";

import type { CompanyDetail, CompanyStory } from "../../shared/api/generated/types.gen";
import { DataTable } from "../../shared/ui/DataTable";
import type { TableColumn } from "../../shared/ui/DataTable";
import { sourceLink } from "../../shared/ui/sourceLink";
import {
  flatMovePercent,
  newsInWindow,
  outlookResults,
  projectionResults,
  projectionSummary,
  sessionClose,
} from "./predictionAnalysis";
import type { OutlookResult, ProjectionResult } from "./predictionAnalysis";

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const signed = (value: number) => `${value > 0 ? "+" : ""}${number.format(value)}`;
const time = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  dateStyle: "medium",
  timeStyle: "short",
});

function NewsEvidence({ news, available }: { news: CompanyStory[]; available: boolean }) {
  if (!available)
    return (
      <Text size="sm" c="dimmed">
        News context requires News access.
      </Text>
    );
  if (!news.length)
    return (
      <Text size="sm" c="dimmed">
        No timestamped linked news in this window among the latest 30 saved articles. Cause not
        established.
      </Text>
    );
  return (
    <Stack gap="xs">
      <Text size="xs" c="dimmed">
        {news.length} linked {news.length === 1 ? "article" : "articles"} in the window; possible
        context, not proven cause.
      </Text>
      {news.map((story, index) => {
        const href = sourceLink(story.url);
        return (
          <div key={`${story.url}-${index}`}>
            {href ? (
              <Anchor href={href} target="_blank" rel="noopener noreferrer" size="sm">
                {story.title}
                <span className="sr-only"> (opens in a new tab)</span>
              </Anchor>
            ) : (
              <Text size="sm">{story.title} (no safe source link)</Text>
            )}
            <Text size="xs" c="dimmed">
              {story.source} | {time.format(new Date(story.published_at!))} IST
              {story.sentiment_score !== null
                ? ` | Sentiment ${signed(story.sentiment_score)}`
                : " | Not scored"}
            </Text>
            {story.sentiment_reason && <Text size="xs">{story.sentiment_reason}</Text>}
          </div>
        );
      })}
    </Stack>
  );
}

function deviationExplanation(result: ProjectionResult) {
  const error = Math.abs(result.error);
  if (error < 0.005)
    return "Observed close matches the projected price to INR 0.01. This does not establish future accuracy.";
  const reversal = result.projectedMove * result.actualMove < 0;
  return `${reversal ? "Price moved against the fitted trend." : "The trend's size or pace did not match the realized move."} Actual return ${signed(result.actualMove)}% vs projected ${signed(result.projectedMove)}% (${signed(result.actualMove - result.projectedMove)} percentage points). The model extrapolates a fixed 20-close slope and does not model news, volatility, market moves or corporate actions. These are model limitations, not evidence of a specific cause.`;
}

function SignalEvidence({ result }: { result: OutlookResult }) {
  const signal = result.signal;
  const momentumWeight = signal.inputs.momentum_weight;
  const newsWeight = signal.inputs.news_weight;
  const momentumContribution =
    typeof momentumWeight === "number" ? momentumWeight * signal.momentum_score : null;
  const newsContribution =
    typeof newsWeight === "number" && signal.news_score !== null
      ? newsWeight * signal.news_score
      : null;
  return (
    <Stack gap="xs">
      <Text size="sm">{result.reason}</Text>
      <Text size="xs" c="dimmed">
        Saved model:{" "}
        {typeof signal.inputs.method === "string" ? signal.inputs.method : "Not recorded"}. Momentum
        score {number.format(signal.momentum_score)}
        {momentumContribution !== null &&
          ` (weighted contribution ${signed(momentumContribution)})`}
        ; news score{" "}
        {signal.news_score === null ? "not available" : number.format(signal.news_score)}
        {newsContribution !== null && ` (weighted contribution ${signed(newsContribution)})`}.{" "}
        Combined score {number.format(signal.score)}.
      </Text>
      {result.state === "Missed" && (
        <Text size="xs">
          The observed direction differed from the saved momentum/news signal. Its backward-looking
          inputs did not capture the target move. New information, market-wide moves or model error
          may matter; a specific cause cannot be determined from price and sentiment alone.
        </Text>
      )}
    </Stack>
  );
}

export function PredictionReview({ data }: { data: CompanyDetail }) {
  const [horizon, setHorizon] = useState(1);
  const results = projectionResults(data.candles, horizon);
  const summary = projectionSummary(results);
  const outlooks = outlookResults(
    data.outlook_history?.length ? data.outlook_history : data.outlook ? [data.outlook] : [],
    data.candles,
  );
  const scored = outlooks.filter(
    (result) => result.state === "Matched" || result.state === "Missed",
  );
  const matched = scored.filter((result) => result.state === "Matched").length;
  const latestMiss = [...results].reverse().find((result) => !result.matched);
  const latest = latestMiss ?? results.at(-1);
  const betterThanBaseline = summary ? summary.mae < summary.baselineMae : false;
  const outlookAccuracy = scored.length ? (matched / scored.length) * 100 : null;
  const projectionColumns: TableColumn<ProjectionResult>[] = [
    {
      id: "target",
      label: "Target / cutoff",
      value: (result) => result.target.day,
      render: (result) => (
        <>
          <Text size="sm" fw={600}>
            {result.target.day}
          </Text>
          <Text size="xs" c="dimmed">
            Cutoff {result.origin.day} close
          </Text>
        </>
      ),
    },
    {
      id: "predicted",
      label: "Projected INR",
      value: (result) => result.predicted,
      render: (result) => number.format(result.predicted),
    },
    {
      id: "actual",
      label: "Actual INR",
      value: (result) => result.target.close,
      render: (result) => number.format(result.target.close),
    },
    {
      id: "error",
      label: "Deviation: actual - projected",
      value: (result) => result.error,
      render: (result) => (
        <>
          <Text size="sm">{signed(result.error)} INR</Text>
          <Text size="xs" c="dimmed">
            {signed(result.errorPercent)}% of actual
          </Text>
        </>
      ),
    },
    {
      id: "direction",
      label: "Direction check",
      value: (result) => (result.matched ? "Matched" : "Missed"),
      render: (result) => (
        <Badge color={result.matched ? "teal" : "orange"}>
          {result.matched ? "Direction matched" : "Direction missed"}
        </Badge>
      ),
    },
    {
      id: "explanation",
      label: "Deviation evidence",
      value: deviationExplanation,
      render: (result) => <Text size="sm">{deviationExplanation(result)}</Text>,
    },
    {
      id: "news",
      label: "News during forecast window",
      sortable: false,
      value: () => null,
      render: (result) => (
        <NewsEvidence
          available={data.news_available}
          news={newsInWindow(
            data.news,
            sessionClose(result.origin.day),
            sessionClose(result.target.day),
          )}
        />
      ),
    },
  ];
  const outlookColumns: TableColumn<OutlookResult>[] = [
    {
      id: "target",
      label: "Target / saved",
      value: (result) => result.signal.target_date,
      render: (result) => (
        <>
          <Text size="sm" fw={600}>
            {result.signal.target_date}
          </Text>
          <Text size="xs" c="dimmed">
            {time.format(new Date(result.signal.created_at))} IST
          </Text>
        </>
      ),
    },
    { id: "direction", label: "Saved direction", value: (result) => result.signal.direction },
    {
      id: "actual",
      label: "Actual move / close",
      value: (result) => result.actualMove,
      render: (result) =>
        result.actualMove === null
          ? "Not available"
          : `${signed(result.actualMove)}% / INR ${number.format(result.actualClose!)}`,
    },
    {
      id: "result",
      label: "Result",
      value: (result) => result.state,
      render: (result) => (
        <Badge
          color={
            result.state === "Matched" ? "teal" : result.state === "Missed" ? "orange" : "gray"
          }
        >
          {result.state}
        </Badge>
      ),
    },
    {
      id: "evidence",
      label: "Model inputs & deviation",
      value: (result) => result.reason,
      render: (result) => <SignalEvidence result={result} />,
    },
    {
      id: "news",
      label: "News after prediction",
      sortable: false,
      value: () => null,
      render: (result) =>
        result.start === null || result.state === "Pending" || result.state === "Not verifiable" ? (
          "No completed verifiable comparison window."
        ) : (
          <NewsEvidence
            available={data.news_available}
            news={newsInWindow(data.news, result.start, sessionClose(result.signal.target_date))}
          />
        ),
    },
  ];
  return (
    <Stack gap="sm" mt="lg" id="prediction-review">
      <Title order={3} size="h4">
        Prediction accuracy &amp; deviations
      </Title>
      <Text size="sm" c="dimmed">
        How past predictions compared with actual prices. Future dashed values are not verified.
      </Text>
      <Paper withBorder p="md">
        <Stack gap="md">
          <Group gap="sm" justify="space-between" align="center">
            <Group gap="xs">
              <Title order={4} size="h5">
                Chart projection
              </Title>
              <Badge variant="light" color="gray">
                Historical simulation
              </Badge>
            </Group>
            <NativeSelect
              label="Forecast horizon"
              value={String(horizon)}
              onChange={(event) => setHorizon(Number(event.target.value))}
              data={[
                { value: "1", label: "Next session" },
                { value: "5", label: "5 sessions ahead" },
                { value: "20", label: "20 sessions ahead" },
              ]}
            />
          </Group>
          {summary ? (
            <>
              <Alert
                color={betterThanBaseline ? "teal" : "orange"}
                title={
                  betterThanBaseline
                    ? "Lower price error than a no-change guess"
                    : summary.mae === summary.baselineMae
                      ? "No improvement over a no-change guess"
                      : "Higher price error than a no-change guess"
                }
              >
                Based on {summary.count} historical{" "}
                {summary.count === 1 ? "comparison" : "comparisons"}. This is a simulation, not a
                live track record.
              </Alert>
              <SimpleGrid
                cols={{ base: 1, sm: 3 }}
                spacing="md"
                aria-label="Projection accuracy summary"
              >
                <div>
                  <Text size="sm" c="dimmed">
                    Direction correct
                  </Text>
                  <Text size="xl" fw={700}>
                    {number.format(summary.directionAccuracy)}%
                  </Text>
                  <Progress
                    value={summary.directionAccuracy}
                    size="sm"
                    aria-label={`Direction correct ${number.format(summary.directionAccuracy)}%`}
                  />
                  <Text size="xs" c="dimmed">
                    {results.filter((result) => result.matched).length} of {summary.count} moves
                    matched
                  </Text>
                </div>
                <div>
                  <Text size="sm" c="dimmed">
                    Average price miss
                  </Text>
                  <Text size="xl" fw={700}>
                    INR {number.format(summary.mae)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    Lower is better · {number.format(summary.mape)}% average error
                  </Text>
                </div>
                <div>
                  <Text size="sm" c="dimmed">
                    If price stayed unchanged
                  </Text>
                  <Text size="xl" fw={700}>
                    INR {number.format(summary.baselineMae)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    Average miss using the cutoff price as the guess
                  </Text>
                </div>
              </SimpleGrid>
              {latest && (
                <Paper withBorder p="md">
                  <Stack gap="sm">
                    <Group justify="space-between">
                      <Title order={5} size="sm">
                        {latestMiss ? "Latest direction miss" : "Latest comparison"} ·{" "}
                        {latest.target.day}
                      </Title>
                      <Badge color={latest.matched ? "teal" : "orange"}>
                        {latest.matched ? "Direction matched" : "Direction missed"}
                      </Badge>
                    </Group>
                    <SimpleGrid cols={{ base: 3 }} spacing="xs">
                      <div>
                        <Text size="xs" c="dimmed">
                          Projected
                        </Text>
                        <Text fw={600}>INR {number.format(latest.predicted)}</Text>
                      </div>
                      <div>
                        <Text size="xs" c="dimmed">
                          Actual
                        </Text>
                        <Text fw={600}>INR {number.format(latest.target.close)}</Text>
                      </div>
                      <div>
                        <Text size="xs" c="dimmed">
                          Difference
                        </Text>
                        <Text fw={600}>{signed(latest.error)} INR</Text>
                      </div>
                    </SimpleGrid>
                    <Text size="sm">
                      {Math.abs(latest.error) < 0.005
                        ? "Price matched the projection to INR 0.01."
                        : `${latest.projectedMove * latest.actualMove < 0 ? "Price moved against the projected trend." : "Price moved by a different amount than projected."} Actual finished INR ${number.format(Math.abs(latest.error))} ${latest.error > 0 ? "above" : "below"} the projection.`}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Related news · possible context, not a confirmed cause
                    </Text>
                    <NewsEvidence
                      available={data.news_available}
                      news={newsInWindow(
                        data.news,
                        sessionClose(latest.origin.day),
                        sessionClose(latest.target.day),
                      ).slice(0, 2)}
                    />
                  </Stack>
                </Paper>
              )}
              <Accordion variant="separated">
                <Accordion.Item value="projection-deviations">
                  <Accordion.Control>
                    Projection deviations &amp; news ({results.length} comparisons)
                  </Accordion.Control>
                  <Accordion.Panel>
                    <DataTable
                      data={results}
                      columns={projectionColumns}
                      label="Projection deviations"
                      initialSort={[{ id: "target", desc: true }]}
                    />
                  </Accordion.Panel>
                </Accordion.Item>
              </Accordion>
            </>
          ) : (
            <Text c="dimmed">
              Not enough completed history to verify this horizon: need at least {20 + horizon}{" "}
              valid saved daily closes. No accuracy is inferred.
            </Text>
          )}
        </Stack>
      </Paper>
      <Paper withBorder p="md">
        <Stack gap="sm">
          <Group gap="xs">
            <Title order={4} size="h5">
              Saved engine outlook
            </Title>
            <Badge color="gray" variant="light">
              Direction only
            </Badge>
          </Group>
          {outlooks.length ? (
            <>
              <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm" aria-label="Saved outlook summary">
                <div>
                  <Text size="sm" c="dimmed">
                    Direction correct
                  </Text>
                  <Text size="xl" fw={700}>
                    {outlookAccuracy === null
                      ? "Not yet scored"
                      : `${number.format(outlookAccuracy)}%`}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {matched} of {scored.length} completed outlooks matched
                  </Text>
                </div>
                <div>
                  <Text size="sm" c="dimmed">
                    Waiting for a result
                  </Text>
                  <Text size="xl" fw={700}>
                    {outlooks.filter((result) => result.state === "Pending").length}
                  </Text>
                  <Text size="xs" c="dimmed">
                    Target session has not finished
                  </Text>
                </div>
                <div>
                  <Text size="sm" c="dimmed">
                    Cannot verify
                  </Text>
                  <Text size="xl" fw={700}>
                    {outlooks.filter((result) => result.state === "Not verifiable").length}
                  </Text>
                  <Text size="xs" c="dimmed">
                    Missing evidence or saved too late
                  </Text>
                </div>
              </SimpleGrid>
              <Accordion variant="separated">
                <Accordion.Item value="outlook-deviations">
                  <Accordion.Control>
                    Saved outlook results &amp; news ({outlooks.length} targets)
                  </Accordion.Control>
                  <Accordion.Panel>
                    <DataTable
                      data={outlooks}
                      columns={outlookColumns}
                      label="Saved outlook verification"
                      initialSort={[{ id: "target", desc: true }]}
                    />
                  </Accordion.Panel>
                </Accordion.Item>
              </Accordion>
            </>
          ) : (
            <Text c="dimmed">
              {data.news_available
                ? "No saved engine outlook history to verify."
                : "Saved engine outlook verification requires News access as well as Markets access."}
            </Text>
          )}
        </Stack>
      </Paper>
      <Text size="xs" c="dimmed">
        Past results do not guarantee future accuracy. News links are context, not proof of cause.
      </Text>
      <Accordion variant="separated">
        <Accordion.Item value="methodology">
          <Accordion.Control>
            How we check predictions &amp; what the numbers mean
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              <Text size="sm">
                <strong>Chart simulation.</strong> Fits only the 20 closes available at each cutoff.
                Latest 60 eligible completed comparisons; not archived forecasts or a live track
                record. Sessions are saved candles, so missing data can stretch the horizon.
                Overlapping windows are not independent.
              </Text>
              <Text size="sm">
                <strong>Direction.</strong> Up, down or flat, using a +/-{flatMovePercent}% flat
                band for both forecast and actual. A correct direction can still have a large price
                miss.
              </Text>
              <Text size="sm">
                <strong>Price error.</strong> Average price miss is MAE (mean absolute error). The
                no-change guess uses the cutoff close on the same samples. MAPE is average absolute
                percentage error against actual close.
              </Text>
              {summary && (
                <Text size="sm">
                  Additional metrics: RMSE INR {number.format(summary.rmse)} (root mean square
                  error); mean deviation {signed(summary.bias)} INR. Positive deviation means actual
                  above projection; negative means below. Negative extrapolated prices remain
                  visible as model failures.
                </Text>
              )}
              <Text size="sm">
                <strong>Saved outlooks.</strong> Earliest saved outlook per target within the latest
                120 records. Excludes pending targets, missing baseline evidence and outlooks saved
                at/after target-session open (09:15 IST). Actual move uses the saved baseline close.
                The flat band is an evaluation convention, not the model's score threshold. A
                direction score is not a price target or probability.
              </Text>
              <Text size="sm">
                <strong>News &amp; causes.</strong> Only timestamped news after cutoff/issuance and
                by target close, among the latest 30 linked saved articles. The highlight shows up
                to two; full tables show all available matches. No matching news does not mean no
                event occurred. Without benchmark prices, corporate actions and event evidence, a
                specific cause remains unknown. Historical data and sentiment may have been revised.
              </Text>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}
