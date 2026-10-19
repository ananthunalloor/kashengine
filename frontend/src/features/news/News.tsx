import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import type { NewsPage } from "../../shared/api/generated/types.gen";
import type { NewsSearch } from "../../shared/api/news";
import { newsSearchSchema } from "../../shared/api/news";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const publishedDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

function sourceLink(url: string): string | undefined {
  if (!URL.canParse(url)) return undefined;
  return ["https:", "http:"].includes(new URL(url).protocol) ? url : undefined;
}

export function News({
  data,
  filters,
  isStaff,
  onFilter,
}: {
  data: NewsPage;
  filters: NewsSearch;
  isStaff: boolean;
  onFilter: (filters: NewsSearch, replace?: boolean) => void;
}) {
  usePageTitle(`News${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const searchInput = useRef<HTMLInputElement>(null);
  const filtered = !!(filters.q || filters.source || filters.sentiment);

  useEffect(() => {
    setQuery(filters.q);
    return () => clearTimeout(timer.current);
  }, [filters.q, filters.source, filters.sentiment, filters.page]);

  function apply(values: NewsSearch, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...values, q: values.q.trim(), page: 1 }, replace);
  }

  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          The stories behind the signal
        </Text>
        <Title order={1} tabIndex={-1}>
          News
        </Title>
        <Text c="dimmed" mt="sm" maw={760}>
          Every article we fetched, with the language model's score and explanation. Sentiment
          ranges from 1.0/10 (very negative for stocks) through 5.5/10 (neutral) to 10.0/10 (very
          positive). Relevance ranges from 1.0/10 to 10.0/10.
        </Text>
        <Anchor href="/news/" size="sm">
          Compare with the existing News page
        </Anchor>
      </header>
      <form
        className="news-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply({ ...filters, q: query });
        }}
      >
        <div>
          <label htmlFor="news-query">Search</label>
          <input
            id="news-query"
            type="search"
            name="q"
            value={query}
            maxLength={100}
            autoComplete="off"
            ref={searchInput}
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => apply({ ...filters, q: value }, true), 300);
            }}
          />
        </div>
        <div>
          <label htmlFor="news-sentiment">Score</label>
          <select
            id="news-sentiment"
            name="sentiment"
            value={filters.sentiment}
            onChange={(event) =>
              apply({
                ...filters,
                q: query,
                sentiment: newsSearchSchema.shape.sentiment.parse(event.target.value),
              })
            }
          >
            <option value="">All</option>
            {data.sentiments.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="news-source">Source</label>
          <select
            id="news-source"
            name="source"
            value={filters.source}
            onChange={(event) => apply({ ...filters, q: query, source: event.target.value })}
          >
            <option value="">All</option>
            {filters.source && !data.sources.includes(filters.source) && (
              <option value={filters.source}>{filters.source} (unavailable)</option>
            )}
            {data.sources.filter(Boolean).map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </div>
        <Group gap="xs">
          <Button type="submit">Apply</Button>
          <Button
            type="button"
            variant="default"
            onClick={() => {
              setQuery("");
              apply({ q: "", sentiment: "", source: "", page: 1 });
              searchInput.current?.focus();
            }}
          >
            Clear filters
          </Button>
        </Group>
      </form>
      <section aria-label="News results">
        <Text size="sm" c="dimmed" role="status" mb="md">
          {data.total} article{data.total === 1 ? "" : "s"}
        </Text>
        {data.items.length ? (
          <ul className="news-list">
            {data.items.map((article) => {
              const href = sourceLink(article.url);
              return (
                <li key={article.id} className="news-card">
                  <div className="news-card-heading">
                    <Title order={2} size="h4">
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {article.title}
                          <span className="sr-only"> (opens in a new tab)</span>
                        </a>
                      ) : (
                        article.title
                      )}
                    </Title>
                    {article.score !== null && (
                      <span
                        className="news-score"
                        data-sentiment={article.sentiment}
                        aria-label={`Sentiment ${article.score}`}
                      >
                        {article.score}
                      </span>
                    )}
                  </div>
                  {!href && (
                    <Text size="xs" c="dimmed">
                      Source link unavailable.
                    </Text>
                  )}
                  <Text size="sm" c="dimmed" mt="xs">
                    {article.source}
                    {article.published_at && (
                      <>
                        ,{" "}
                        <time dateTime={article.published_at}>
                          {publishedDate.format(new Date(article.published_at))} IST
                        </time>
                      </>
                    )}
                    {article.relevance !== null && `, relevance ${article.relevance}`}
                    {article.score === null && " · Not scored yet"}
                  </Text>
                  {article.reason && (
                    <Text size="sm" mt="sm">
                      {article.reason}
                    </Text>
                  )}
                  {!!article.companies.length && (
                    <Text size="sm" c="dimmed" mt="xs">
                      {article.companies.join(", ")}
                    </Text>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="news-card">
            <Text c="dimmed">
              No article matches. Change the search, or clear the filters.
              {isStaff && !filtered && (
                <>
                  {" "}
                  Admins: check the <Anchor href="/ops/feeds/">feeds</Anchor> and start "Fetch news
                  feeds" on the <Anchor href="/ops/jobs/">Jobs</Anchor> page.
                </>
              )}
            </Text>
          </div>
        )}
      </section>
      {data.pages > 1 && (
        <nav aria-label="News pages" className="report-pagination">
          <span>
            {data.page > 1 && (
              <Link to="/news/" search={{ ...filters, page: data.page - 1 }}>
                Newer
              </Link>
            )}
          </span>
          <Text size="sm" c="dimmed">
            Page {data.page} of {data.pages}
          </Text>
          <span>
            {data.page < data.pages && (
              <Link to="/news/" search={{ ...filters, page: data.page + 1 }}>
                Older
              </Link>
            )}
          </span>
        </nav>
      )}
    </Stack>
  );
}
