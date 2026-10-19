import { Anchor, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { LuArrowDownRight, LuArrowRight, LuArrowUpRight, LuHouse } from "react-icons/lu";

import type { Session, Today as TodayData } from "../../shared/api/generated/types.gen";
import { DataTable } from "../../shared/ui/DataTable";
import { displayNumber } from "../../shared/ui/displayNumber";
import { MetricValue, StrengthLegend } from "../../shared/ui/MetricValue";
import { sourceLink } from "../../shared/ui/sourceLink";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { formatReportDate } from "../../shared/ui/formatReportDate";
import { MarketCloses, MarketDate } from "../markets/MarketCloses";

export function Today({ data, session }: { data: TodayData; session: Session }) {
  usePageTitle("Today");
  const { markets, news, ipos, report } = data;
  const outlook = markets?.outlook;
  const DirectionIcon =
    outlook?.direction === "up"
      ? LuArrowUpRight
      : outlook?.direction === "down"
        ? LuArrowDownRight
        : LuArrowRight;
  const stories = news
    ? [
        ...news.good.map((story) => ({ ...story, sentiment: "Good for stocks" })),
        ...news.bad.map((story) => ({ ...story, sentiment: "Bad for stocks" })),
      ]
    : [];
  const issues = ipos
    ? [
        ...ipos.likely_good.map((issue) => ({ ...issue, group: "Likely to do well" })),
        ...ipos.open_now.map((issue) => ({ ...issue, group: "Open now" })),
        ...ipos.upcoming.map((issue) => ({ ...issue, group: "Opening soon" })),
      ]
    : [];
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuHouse aria-hidden="true" /> Your daily perspective
        </Text>
        <Title order={1} tabIndex={-1}>
          Today
        </Title>
        <Text c="dimmed" mt="sm">
          <time dateTime={data.today}>{formatReportDate(data.today)}</time>
          {" · "}Your latest saved outlook, stories, and issues.
        </Text>
        <Anchor href="/dashboard/" size="sm">
          Compare with the original Today page
        </Anchor>
      </header>

      {!session.features.length && (
        <section className="news-card" aria-label="Your access">
          <Title order={2} size="h3">
            Welcome
          </Title>
          <Text c="dimmed" mt="sm">
            No feature is on for your account. See the <Anchor href="/account/">Account</Anchor>{" "}
            page.
          </Text>
        </section>
      )}
      {session.features.length > 0 && !markets && !news && !ipos && !report && (
        <section className="news-card" aria-label="Your overview">
          <Text c="dimmed">
            The daily overview has no available sections or saved reports to show. Open your
            available sections from the navigation.
          </Text>
        </section>
      )}
      {markets && (
        <>
          <section className="news-card today-outlook" aria-labelledby="today-outlook">
            {outlook ? (
              <>
                <Text c="dimmed" size="sm">
                  Outlook for <time dateTime={outlook.date}>{formatReportDate(outlook.date)}</time>
                </Text>
                <div className="today-direction">
                  <span className="report-outlook" data-tone={outlook.direction}>
                    <DirectionIcon aria-hidden="true" />
                  </span>
                  <Title order={2} id="today-outlook">
                    The Nifty 50 is likely to{" "}
                    {outlook.direction === "up"
                      ? "rise"
                      : outlook.direction === "down"
                        ? "fall"
                        : "stay flat"}
                    .
                  </Title>
                </div>
                <dl className="market-summary">
                  <div>
                    <dt>Signal strength ({outlook.strength_label})</dt>
                    <dd>
                      <MetricValue kind="strength" value={outlook.strength} />
                    </dd>
                  </div>
                  <div>
                    <dt>News, from {outlook.news_articles} articles</dt>
                    <dd>
                      <MetricValue kind="score" value={outlook.news_score} />
                    </dd>
                  </div>
                  <div>
                    <dt>Global markets</dt>
                    <dd>
                      <MetricValue kind="score" value={outlook.global_score} />
                    </dd>
                  </div>
                </dl>
                <Text size="sm" c="dimmed" mt="md">
                  Scores run from 1.0 to 10.0. News and global scores are neutral at 5.5.{" "}
                  <StrengthLegend />
                </Text>
                {outlook.notes.map((note, index) => (
                  <Text key={index} size="sm" c="dimmed" mt="sm">
                    {note}
                  </Text>
                ))}
                {outlook.cues.length > 0 && (
                  <div className="today-cues">
                    <DataTable
                      data={outlook.cues}
                      label="Strongest saved cues (up to 5)"
                      columns={[
                        { id: "name", label: "Instrument", value: (row) => row.name },
                        {
                          id: "change",
                          label: "Change",
                          value: (row) => displayNumber(row.change),
                          render: (row) => <MetricValue kind="change" value={row.change} />,
                        },
                        {
                          id: "as_of",
                          label: "Trading date",
                          value: (row) => row.as_of,
                          render: (row) => (
                            <time dateTime={row.as_of}>{formatReportDate(row.as_of)}</time>
                          ),
                        },
                      ]}
                    />
                  </div>
                )}
              </>
            ) : (
              <>
                <Title order={2} id="today-outlook">
                  No outlook yet
                </Title>
                <Text c="dimmed" mt="sm">
                  The prediction is made each morning before the report.
                  {session.is_staff && (
                    <>
                      {" "}
                      Admins: use the <Anchor href="/ops/jobs/">Jobs</Anchor> page to make one.
                    </>
                  )}
                </Text>
              </>
            )}
          </section>
          <Text c="dimmed" size="sm">
            {markets.stats.total ? (
              <>
                The prediction was right on {markets.stats.correct} of {markets.stats.total} days (
                {markets.stats.accuracy}). Guessing the most common result every day would be right{" "}
                {markets.stats.baseline_accuracy}.
                {!markets.stats.enough_results &&
                  " There are too few results to trust these numbers."}
              </>
            ) : (
              "There are no results yet to check the prediction against."
            )}{" "}
            <Link to="/markets/">See the history</Link>.
          </Text>
        </>
      )}
      {news && (
        <section aria-labelledby="today-news">
          <Title order={2} id="today-news" size="h3">
            Stories that move the market
          </Title>
          <Text c="dimmed" size="sm" mt="sm" mb="md">
            The last 36 hours. {news.articles} scored {news.articles === 1 ? "article" : "articles"}
            , {news.positive} good and {news.negative} bad. Up to four strongest stories per
            sentiment.
          </Text>
          <DataTable
            data={stories}
            label="Strongest stories (last 36 hours)"
            filters={[
              {
                label: "Sentiment",
                value: (row) => row.sentiment,
                options: ["Good for stocks", "Bad for stocks"],
              },
            ]}
            empty={
              stories.length
                ? undefined
                : "No strong stories yet. The news is fetched and scored through the day."
            }
            columns={[
              {
                id: "title",
                label: "Story & context",
                value: (row) => `${row.title} ${row.reason} ${row.companies.join(" ")}`,
                render: (row) => {
                  const href = sourceLink(row.url);
                  return (
                    <div className="table-story">
                      <div className="table-primary">
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer">
                            {row.title}
                            <span className="sr-only"> (opens in a new tab)</span>
                          </a>
                        ) : (
                          row.title
                        )}
                      </div>
                      {!href && (
                        <Text size="xs" c="dimmed">
                          Source link unavailable.
                        </Text>
                      )}
                      {row.reason && (
                        <Text size="sm" mt="sm">
                          {row.reason}
                        </Text>
                      )}
                      {row.companies.length > 0 && (
                        <Text size="sm" c="dimmed" mt="xs">
                          {row.companies.join(", ")}
                        </Text>
                      )}
                    </div>
                  );
                },
              },
              { id: "source", label: "Source", value: (row) => row.source },
              { id: "sentiment", label: "Sentiment", value: (row) => row.sentiment },
              {
                id: "score",
                label: "Score",
                value: (row) => displayNumber(row.score),
                render: (row) => <MetricValue kind="score" value={row.score} />,
              },
            ]}
          />
          <Text size="sm" mt="md">
            <Link to="/news/" search={{ q: "", source: "", sentiment: "", page: 1 }}>
              All news
            </Link>
          </Text>
        </section>
      )}
      {ipos && (
        <section aria-labelledby="today-ipos">
          <Title order={2} id="today-ipos" size="h3">
            IPOs
          </Title>
          <Text c="dimmed" size="sm" mt="sm" mb="md">
            Open issues and those opening in the next {ipos.days_ahead} days. Up to four per group;
            each issue appears once.
          </Text>
          <DataTable
            data={issues}
            label="IPO watchlist"
            filters={[
              {
                label: "Group",
                value: (row) => row.group,
                options: ["Likely to do well", "Open now", "Opening soon"],
              },
            ]}
            empty={issues.length ? undefined : "No IPO is open or coming soon."}
            columns={[
              { id: "name", label: "Issue", value: (row) => row.name },
              { id: "group", label: "Group", value: (row) => row.group },
              {
                id: "category",
                label: "Board",
                value: (row) => (row.category === "sme" ? "SME" : "Mainboard"),
              },
              {
                id: "open_date",
                label: "Opens",
                value: (row) => row.open_date,
                render: (row) => (row.open_date ? <MarketDate day={row.open_date} /> : "\u2013"),
              },
              {
                id: "close_date",
                label: "Closes",
                value: (row) => row.close_date,
                render: (row) => (row.close_date ? <MarketDate day={row.close_date} /> : "\u2013"),
              },
              {
                id: "price_band",
                label: "Price up to",
                value: (row) => row.price_band,
                sortable: false,
              },
              {
                id: "gmp",
                label: "GMP",
                value: (row) => displayNumber(row.gmp),
                render: (row) => <MetricValue kind="change" value={row.gmp} />,
              },
              {
                id: "subscribed",
                label: "Subscribed",
                value: (row) => displayNumber(row.subscribed),
                render: (row) => row.subscribed,
              },
              {
                id: "verdict",
                label: "Verdict",
                value: (row) => row.verdict,
                render: (row) => (
                  <span className="ipo-verdict" data-verdict={row.verdict}>
                    {row.verdict.charAt(0).toUpperCase() + row.verdict.slice(1)}
                  </span>
                ),
              },
              {
                id: "score",
                label: "Score",
                value: (row) => (row.score === null ? null : displayNumber(row.score)),
                render: (row) => <MetricValue kind="score" value={row.score} />,
              },
            ]}
          />
          <Text size="sm" mt="md">
            <Link to="/ipos/" search={{ q: "", status: "", verdict: "", category: "", page: 1 }}>
              All IPOs
            </Link>
          </Text>
        </section>
      )}
      {markets && (
        <section aria-labelledby="today-closes">
          <Title order={2} id="today-closes" size="h3" mb="md">
            Last close
          </Title>
          <MarketCloses quotes={markets.quotes} label="Latest saved closes" />
        </section>
      )}
      {report && (
        <section className="news-card" aria-label="Latest report">
          <Text size="sm">
            The latest report is from {formatReportDate(report.date)}.{" "}
            <Link to="/reports/$day/" params={{ day: report.date }}>
              Read it
            </Link>
            .
          </Text>
        </section>
      )}
    </Stack>
  );
}
