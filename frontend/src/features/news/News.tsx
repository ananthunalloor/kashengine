import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuNewspaper, LuSlidersHorizontal, LuX } from "react-icons/lu";

import type { NewsPage } from "../../shared/api/generated/types.gen";
import type { NewsSearch } from "../../shared/api/news";
import { newsSearchSchema } from "../../shared/api/news";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { sourceLink } from "../../shared/ui/sourceLink";
import { DataTable } from "../../shared/ui/DataTable";
import { MetricValue } from "../../shared/ui/MetricValue";

const publishedDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

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
  }, [filters.q, filters.source, filters.sentiment, filters.page, filters.sort, filters.page_size]);

  function apply(values: NewsSearch, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...values, q: values.q.trim(), page: 1 }, replace);
  }

  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuNewspaper aria-hidden="true" />
          The stories behind the signal
        </Text>
        <Title order={1} tabIndex={-1}>
          News
        </Title>
        <Text c="dimmed" mt="sm" maw={760}>
          Every article we fetched, with the language model's score and explanation. Sentiment
          ranges from 1.0/10 (very negative for stocks) through 5.5/10 (neutral) to 10.0/10 (very
          positive). Relevance ranges from 1.0/10 to 10.0/10: green at 6.4 or above, amber below,
          and neutral when unavailable. Relevance is not market direction.
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
          <Button type="submit" leftSection={<LuSlidersHorizontal aria-hidden="true" />}>
            Apply
          </Button>
          <Button
            type="button"
            variant="default"
            leftSection={<LuX aria-hidden="true" />}
            onClick={() => {
              setQuery("");
              apply({ ...filters, q: "", sentiment: "", source: "", page: 1 });
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
        <DataTable
          data={data.items}
          label="News"
          columns={[
            {
              id: "title",
              label: "Article & context",
              value: (row) => row.title,
              render: (article) => {
                const href = sourceLink(article.url);
                return (
                  <div className="table-story">
                    <div className="table-primary">
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {article.title}
                          <span className="sr-only"> (opens in a new tab)</span>
                        </a>
                      ) : (
                        article.title
                      )}
                    </div>
                    {!href && (
                      <Text size="xs" c="dimmed">
                        Source link unavailable.
                      </Text>
                    )}
                    {article.score === null && (
                      <Text size="sm" c="dimmed">
                        Not scored yet
                      </Text>
                    )}
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
                  </div>
                );
              },
            },
            { id: "source", label: "Source", value: (row) => row.source },
            {
              id: "published_at",
              label: "Published",
              value: (row) => row.published_at,
              render: (row) =>
                row.published_at ? (
                  <time dateTime={row.published_at}>
                    {publishedDate.format(new Date(row.published_at))} IST
                  </time>
                ) : (
                  "Not available"
                ),
            },
            {
              id: "score",
              label: "Sentiment",
              value: (row) => row.score,
              render: (row) =>
                row.score === null ? (
                  "Not scored"
                ) : (
                  <span
                    className="news-score"
                    data-sentiment={row.sentiment}
                    aria-label={`Sentiment ${row.score}`}
                  >
                    {row.score}
                  </span>
                ),
            },
            {
              id: "relevance",
              label: "Relevance",
              value: (row) => row.relevance,
              render: (row) => <MetricValue kind="relevance" value={row.relevance} />,
            },
          ]}
          server={{
            page: data.page,
            pages: data.pages,
            total: data.total,
            pageSize: data.page_size ?? 25,
            sort: filters.sort,
            onSort: (sort) => apply({ ...filters, q: query, sort }),
            onPageSize: (page_size) => apply({ ...filters, q: query, page_size }),
            paginationLabel: "News pages",
            pageLink: (page, label) => (
              <Link to="/news/" search={{ ...filters, page }}>
                {label}
              </Link>
            ),
          }}
          empty={
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
          }
        />
      </section>
    </Stack>
  );
}
