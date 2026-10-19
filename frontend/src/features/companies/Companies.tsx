import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import type { CompanySearch } from "../../shared/api/companies";
import type { CompanyPage } from "../../shared/api/generated/types.gen";
import { sourceLink } from "../../shared/ui/sourceLink";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const fetchedDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function Companies({
  data,
  filters,
  isStaff,
  onFilter,
}: {
  data: CompanyPage;
  filters: CompanySearch;
  isStaff: boolean;
  onFilter: (filters: CompanySearch, replace?: boolean) => void;
}) {
  usePageTitle(`Companies${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const searchInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setQuery(filters.q);
    return () => clearTimeout(timer.current);
  }, [filters.q, filters.page]);

  function apply(q: string, replace = false) {
    clearTimeout(timer.current);
    onFilter({ q: q.trim(), page: 1 }, replace);
  }

  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          The companies behind the stories
        </Text>
        <Title order={1} tabIndex={-1}>
          Companies
        </Title>
        <Text c="dimmed" mt="sm">
          The companies that we link to news. Data comes from Screener.in.
        </Text>
        <Anchor href="/companies/" size="sm">
          Compare with the existing Companies page
        </Anchor>
      </header>
      <form
        className="news-filters company-filters"
        onSubmit={(event) => {
          event.preventDefault();
          apply(query);
        }}
      >
        <div>
          <label htmlFor="company-query">Search by name, symbol, or sector</label>
          <input
            id="company-query"
            type="search"
            name="q"
            maxLength={100}
            autoComplete="off"
            value={query}
            ref={searchInput}
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              clearTimeout(timer.current);
              timer.current = setTimeout(() => apply(value, true), 300);
            }}
          />
        </div>
        <Group gap="xs">
          <Button type="submit">Search</Button>
          <Button
            type="button"
            variant="default"
            onClick={() => {
              setQuery("");
              apply("");
              searchInput.current?.focus();
            }}
          >
            Clear search
          </Button>
        </Group>
      </form>
      <section aria-label="Company results">
        <Text size="sm" c="dimmed" role="status" mb="md">
          {data.total} {data.total === 1 ? "company" : "companies"}
        </Text>
        {data.items.length ? (
          <ul className="news-list">
            {data.items.map((company) => {
              const href = sourceLink(company.screener_url);
              return (
                <li className="news-card" key={company.id}>
                  <Title order={2} size="h4">
                    {href ? (
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        {company.name}
                        <span className="sr-only"> (opens in a new tab)</span>
                      </a>
                    ) : (
                      company.name
                    )}
                  </Title>
                  {!href && (
                    <Text c="dimmed" size="xs">
                      Source link unavailable.
                    </Text>
                  )}
                  <dl className="company-facts">
                    <div>
                      <dt>Symbol</dt>
                      <dd>{company.symbol}</dd>
                    </div>
                    <div>
                      <dt>Sector</dt>
                      <dd>{company.sector || "Not available"}</dd>
                    </div>
                    <div>
                      <dt>Data from</dt>
                      <dd>
                        {company.last_updated ? (
                          <time dateTime={company.last_updated}>
                            {fetchedDate.format(new Date(company.last_updated))}
                          </time>
                        ) : (
                          "Not fetched"
                        )}
                      </dd>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="news-card">
            <Text c="dimmed">
              No company matches. Change the search, or clear it.
              {isStaff && !filters.q && (
                <>
                  {" "}
                  Admins: add companies with <code>python manage.py import_companies</code>.
                </>
              )}
            </Text>
          </div>
        )}
      </section>
      {data.pages > 1 && (
        <nav aria-label="Company pages" className="report-pagination">
          <span>
            {data.page > 1 && (
              <Link to="/companies/" search={{ ...filters, page: data.page - 1 }}>
                Previous
              </Link>
            )}
          </span>
          <Text c="dimmed" size="sm">
            Page {data.page} of {data.pages}
          </Text>
          <span>
            {data.page < data.pages && (
              <Link to="/companies/" search={{ ...filters, page: data.page + 1 }}>
                Next
              </Link>
            )}
          </span>
        </nav>
      )}
    </Stack>
  );
}
