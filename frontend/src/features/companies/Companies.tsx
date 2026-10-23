import { Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuBuilding2, LuSearch, LuX } from "react-icons/lu";

import type { CompanySearch } from "../../shared/api/companies";
import type { CompanyPage } from "../../shared/api/generated/types.gen";
import { sourceLink } from "../../shared/ui/sourceLink";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { DataTable } from "../../shared/ui/DataTable";
import { TableFilterField, TableFilters } from "../../shared/ui/TableFilters";

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
  }, [filters.q, filters.page, filters.sector, filters.sort, filters.page_size]);

  function apply(q: string, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...filters, q: q.trim(), page: 1 }, replace);
  }

  function changeTable(values: CompanySearch) {
    clearTimeout(timer.current);
    onFilter({ ...values, q: query.trim(), page: 1 });
  }

  const filterControls = (
    <TableFilters
      onSubmit={(event) => {
        event.preventDefault();
        apply(query);
      }}
    >
      <TableFilterField search label="Search by name, symbol, or sector" htmlFor="company-query">
        <input
          id="company-query"
          type="search"
          name="q"
          maxLength={100}
          autoComplete="off"
          placeholder="Search name, symbol, or sector..."
          value={query}
          ref={searchInput}
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
            clearTimeout(timer.current);
            timer.current = setTimeout(() => apply(value, true), 300);
          }}
        />
      </TableFilterField>
      <TableFilterField label="Sector" htmlFor="company-sector">
        <select
          id="company-sector"
          value={filters.sector ?? ""}
          onChange={(event) => {
            clearTimeout(timer.current);
            onFilter({ ...filters, q: query.trim(), sector: event.target.value, page: 1 });
          }}
        >
          <option value="">All sectors</option>
          {filters.sector && !data.sectors?.includes(filters.sector) && (
            <option>{filters.sector}</option>
          )}
          {data.sectors?.map((sector) => (
            <option key={sector}>{sector}</option>
          ))}
        </select>
      </TableFilterField>
      <Group gap="xs">
        <Button type="submit" leftSection={<LuSearch aria-hidden="true" />}>
          Search
        </Button>
        <Button
          type="button"
          variant="default"
          leftSection={<LuX aria-hidden="true" />}
          onClick={() => {
            setQuery("");
            clearTimeout(timer.current);
            onFilter({ ...filters, q: "", sector: undefined, page: 1 });
            searchInput.current?.focus();
          }}
        >
          Clear search
        </Button>
      </Group>
    </TableFilters>
  );
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuBuilding2 aria-hidden="true" />
          The companies behind the stories
        </Text>
        <Title order={1}>Companies</Title>
        <Text c="dimmed" mt="sm">
          Saved company details, fundamentals, prices, trends and score evidence.
        </Text>
        <Anchor href="/companies/" size="sm">
          Compare with the existing Companies page
        </Anchor>
      </header>
      <section aria-label="Company results">
        <Text size="sm" c="dimmed" role="status" mb="md">
          {data.total} {data.total === 1 ? "company" : "companies"}
        </Text>
        <DataTable
          data={data.items}
          label="Companies"
          filterControls={filterControls}
          columns={[
            {
              id: "name",
              label: "Company",
              value: (row) => row.name,
              render: (company) => {
                const href = sourceLink(company.screener_url);
                return (
                  <div className="table-primary">
                    <Link to="/companies/$id/" params={{ id: String(company.id) }}>
                      {company.name}
                    </Link>
                    {href && (
                      <Text size="xs">
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          Screener source<span className="sr-only"> (opens in a new tab)</span>
                        </a>
                      </Text>
                    )}
                    {!href && (
                      <Text c="dimmed" size="xs">
                        Source link unavailable.
                      </Text>
                    )}
                  </div>
                );
              },
            },
            {
              id: "symbol",
              label: "Symbol",
              value: (row) => row.symbol,
              render: (row) => <span className="symbol-chip">{row.symbol}</span>,
            },
            {
              id: "sector",
              label: "Sector",
              value: (row) => row.sector,
              render: (row) => row.sector || "Not available",
            },
            {
              id: "last_updated",
              label: "Data from",
              value: (row) => row.last_updated,
              render: (row) =>
                row.last_updated ? (
                  <time dateTime={row.last_updated}>
                    {fetchedDate.format(new Date(row.last_updated))}
                  </time>
                ) : (
                  "Not fetched"
                ),
            },
          ]}
          server={{
            page: data.page,
            pages: data.pages,
            total: data.total,
            pageSize: data.page_size ?? 25,
            sort: filters.sort,
            onSort: (sort) => changeTable({ ...filters, sort }),
            onPageSize: (page_size) => changeTable({ ...filters, page_size }),
            paginationLabel: "Company pages",
            pageLink: (page, label) => (
              <Link to="/companies/" search={{ ...filters, page }}>
                {label}
              </Link>
            ),
          }}
          empty={
            <Text c="dimmed">
              No company matches. Change the search, or clear it.
              {isStaff && !filters.q && !filters.sector && (
                <>
                  {" "}
                  Admins: add companies with <code>python manage.py import_companies</code>.
                </>
              )}
            </Text>
          }
        />
      </section>
    </Stack>
  );
}
