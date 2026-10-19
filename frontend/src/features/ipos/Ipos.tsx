import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuActivity, LuSlidersHorizontal, LuX } from "react-icons/lu";

import type { IpoDetail, IpoPage, IpoSummary } from "../../shared/api/generated/types.gen";
import { ipoSearchSchema } from "../../shared/api/ipos";
import type { IpoSearch } from "../../shared/api/ipos";
import { sourceLink } from "../../shared/ui/sourceLink";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { DataTable } from "../../shared/ui/DataTable";
import { displayNumber } from "../../shared/ui/displayNumber";
import { MetricValue } from "../../shared/ui/MetricValue";

const scoredDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

function Verdict({ ipo, withScore = false }: { ipo: IpoSummary; withScore?: boolean }) {
  return (
    <span className="ipo-verdict" data-verdict={ipo.verdict}>
      {ipo.verdict.charAt(0).toUpperCase() + ipo.verdict.slice(1)}
      {withScore && ipo.score !== null && (
        <>
          , score <MetricValue kind="score" value={ipo.score} />
        </>
      )}
    </span>
  );
}

export function Ipos({
  data,
  filters,
  isStaff,
  onFilter,
}: {
  data: IpoPage;
  filters: IpoSearch;
  isStaff: boolean;
  onFilter: (value: IpoSearch, replace?: boolean) => void;
}) {
  usePageTitle(`IPOs${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setQuery(filters.q);
    return () => clearTimeout(timer.current);
  }, [
    filters.q,
    filters.status,
    filters.verdict,
    filters.category,
    filters.page,
    filters.sort,
    filters.page_size,
  ]);
  function apply(value: IpoSearch, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...value, q: value.q.trim(), page: 1 }, replace);
  }
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuActivity aria-hidden="true" />
          IPO intelligence
        </Text>
        <Title order={1} tabIndex={-1}>
          IPOs
        </Title>
        <Text c="dimmed" mt="sm" maw={760}>
          The verdict comes from GMP, final subscription, and news. The rule is a first guess, and
          GMP is not official data.
        </Text>
        <Anchor href="/ipos/" size="sm">
          Compare with the existing IPO pages
        </Anchor>
      </header>
      <form
        className="news-filters ipo-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply({ ...filters, q: query });
        }}
      >
        <div>
          <label htmlFor="ipo-query">Search</label>
          <input
            id="ipo-query"
            type="search"
            maxLength={100}
            autoComplete="off"
            ref={input}
            value={query}
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => apply({ ...filters, q: value }, true), 300);
            }}
          />
        </div>
        <div>
          <label htmlFor="ipo-status">Status</label>
          <select
            id="ipo-status"
            value={filters.status}
            onChange={(event) =>
              apply({
                ...filters,
                q: query,
                status: ipoSearchSchema.shape.status.parse(event.target.value),
              })
            }
          >
            {data.statuses.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ipo-verdict">Verdict</label>
          <select
            id="ipo-verdict"
            value={filters.verdict}
            onChange={(event) =>
              apply({
                ...filters,
                q: query,
                verdict: ipoSearchSchema.shape.verdict.parse(event.target.value),
              })
            }
          >
            <option value="">All</option>
            {data.verdicts.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ipo-category">Board</label>
          <select
            id="ipo-category"
            value={filters.category}
            onChange={(event) =>
              apply({
                ...filters,
                q: query,
                category: ipoSearchSchema.shape.category.parse(event.target.value),
              })
            }
          >
            <option value="">All</option>
            {data.categories.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
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
              apply({ ...filters, q: "", status: "", verdict: "", category: "", page: 1 });
              input.current?.focus();
            }}
          >
            Clear filters
          </Button>
        </Group>
      </form>
      <section aria-label="IPO results">
        <Text role="status" size="sm" c="dimmed" mb="md">
          {data.total} IPO{data.total === 1 ? "" : "s"}
        </Text>
        <DataTable
          data={data.items}
          label="IPOs"
          columns={[
            {
              id: "name",
              label: "Issue",
              value: (row) => row.name,
              render: (row) => (
                <Link className="table-primary" to="/ipos/$id/" params={{ id: String(row.id) }}>
                  {row.name}
                </Link>
              ),
            },
            { id: "category", label: "Board", value: (row) => row.category },
            {
              id: "status",
              label: "Status",
              value: (row) => row.status,
              render: (row) => <span className="report-status">{row.status}</span>,
            },
            { id: "dates", label: "Dates", value: (row) => row.dates },
            { id: "price_band", label: "Price band", value: (row) => row.price_band },
            {
              id: "gmp",
              label: "GMP",
              value: (row) => row.gmp,
              render: (row) => <MetricValue kind="change" value={row.gmp} />,
            },
            { id: "subscribed", label: "Subscribed", value: (row) => row.subscribed },
            {
              id: "listing_gain",
              label: "Listing gain",
              value: (row) => row.listing_gain,
              render: (row) => <MetricValue kind="change" value={row.listing_gain} />,
            },
            {
              id: "verdict",
              label: "Verdict",
              value: (row) => row.verdict,
              render: (row) => <Verdict ipo={row} />,
            },
            {
              id: "score",
              label: "Score",
              value: (row) => row.score,
              render: (row) => <MetricValue kind="score" value={row.score} />,
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
            paginationLabel: "IPO pages",
            pageLink: (page, label) => (
              <Link to="/ipos/" search={{ ...filters, page }}>
                {label}
              </Link>
            ),
          }}
          empty={
            <Text c="dimmed">
              No IPO matches. Change the filters.
              {isStaff && !filters.q && (
                <>
                  {" "}
                  Admins: turn on the IPO list in{" "}
                  <Anchor href="/ops/settings/ipos/">Ops &gt; Settings &gt; IPOs</Anchor> and start
                  "Collect IPOs" on the <Anchor href="/ops/jobs/">Jobs</Anchor> page.
                </>
              )}
            </Text>
          }
        />
      </section>
    </Stack>
  );
}

export function IpoView({ ipo }: { ipo: IpoDetail }) {
  usePageTitle(ipo.name);
  const href = sourceLink(ipo.source_url);
  return (
    <Stack gap="xl">
      <header>
        <Link to="/ipos/" search={{ q: "", status: "", verdict: "", category: "", page: 1 }}>
          All IPOs
        </Link>
        <Text className="app-eyebrow" mt="lg" mb="xs">
          The issue, in context
        </Text>
        <Title order={1} tabIndex={-1}>
          {ipo.name}
        </Title>
        <Text c="dimmed" mt="xs" mb="sm">
          {ipo.category}, {ipo.status}
        </Text>
        <Verdict ipo={ipo} withScore />
      </header>
      <div className="ipo-detail-grid">
        <section aria-labelledby="ipo-facts-title" className="news-card">
          <Title order={2} size="h3" id="ipo-facts-title">
            The issue
          </Title>
          <dl className="ipo-facts">
            {ipo.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>
                  {fact.label === "GMP" || fact.label === "Listing gain" ? (
                    <MetricValue kind="change" value={fact.value.replace(/^(?:₹|Rs\s*)/, "")}>
                      {fact.value}
                    </MetricValue>
                  ) : (
                    fact.value
                  )}
                </dd>
              </div>
            ))}
          </dl>
          {href && (
            <Anchor href={href} target="_blank" rel="noopener noreferrer" size="sm">
              Source page (opens in a new tab)
            </Anchor>
          )}
          {ipo.source_url && !href && (
            <Text size="sm" c="dimmed">
              Source link unavailable.
            </Text>
          )}
        </section>
        <section aria-labelledby="ipo-score-title" className="news-card">
          <Title order={2} size="h3" id="ipo-score-title">
            How the verdict was made
          </Title>
          <Text size="sm" c="dimmed" mt="sm">
            Scores run from 1.0/10 (most negative) through 5.5/10 (neutral) to 10.0/10 (most
            positive). GMP and subscription values keep their original units.
          </Text>
          {ipo.signals.length ? (
            <DataTable
              data={ipo.signals}
              label="Saved scoring inputs"
              columns={[
                { id: "name", label: "Signal", value: (row) => row.name },
                {
                  id: "value",
                  label: "Value",
                  value: (row) => row.value,
                  sortable: false,
                  render: (row) =>
                    row.name === "GMP" || row.name === "News" ? (
                      <MetricValue
                        kind={row.name === "GMP" ? "change" : "score"}
                        value={row.value}
                      />
                    ) : (
                      row.value
                    ),
                },
                {
                  id: "signal",
                  label: "Signal (1-10)",
                  value: (row) => displayNumber(row.signal),
                  render: (row) => <MetricValue kind="score" value={row.signal} />,
                },
              ]}
            />
          ) : (
            <Text c="dimmed" mt="md">
              There is no usable signal yet.
            </Text>
          )}
          {ipo.notes.map((note, index) => (
            <Text key={index} size="sm" c="dimmed" mt="sm">
              {note}
            </Text>
          ))}
          {ipo.scored_at && (
            <Text size="sm" c="dimmed" mt="md">
              Scored{" "}
              <time dateTime={ipo.scored_at}>{scoredDate.format(new Date(ipo.scored_at))} IST</time>
              .
            </Text>
          )}
          <Text size="sm" c="dimmed" mt="md">
            GMP is unofficial data. This verdict is not investment advice.
          </Text>
        </section>
      </div>
    </Stack>
  );
}
