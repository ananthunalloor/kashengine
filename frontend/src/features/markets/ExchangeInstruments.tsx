import { Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { LuSearch } from "react-icons/lu";

import type { ExchangeInstrumentSearch } from "../../shared/api/exchangeInstruments";
import type { ExchangeInstrumentPage } from "../../shared/api/generated/types.gen";
import { DataTable } from "../../shared/ui/DataTable";
import { TableFilterField, TableFilters } from "../../shared/ui/TableFilters";
import { usePageTitle } from "../../shared/ui/usePageTitle";

const expiryDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});

export function ExchangeInstruments({
  data,
  filters,
  onFilter,
}: {
  data: ExchangeInstrumentPage;
  filters: ExchangeInstrumentSearch;
  onFilter: (filters: ExchangeInstrumentSearch) => void;
}) {
  usePageTitle(`Exchange instruments${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  useEffect(() => setQuery(filters.q), [filters.q]);

  function apply(values: Partial<ExchangeInstrumentSearch>) {
    onFilter({ ...filters, ...values, page: 1 });
  }

  return (
    <Stack gap="xl">
      <header>
        <Link to="/markets/">Markets and predictions</Link>
        <Title order={1} mt="sm">
          NSE &amp; BSE instruments
        </Title>
        <Text c="dimmed" mt="sm">
          Search active equity shares, indices, futures and options in the latest imported Upstox
          instrument master. This catalog lists instruments; it does not imply saved or live prices.
        </Text>
      </header>
      <Text size="sm" c="dimmed" role="status">
        {data.total.toLocaleString("en-IN")} {data.total === 1 ? "instrument" : "instruments"}
      </Text>
      <DataTable
        data={data.items}
        label="NSE and BSE instruments"
        filterControls={
          <TableFilters
            onSubmit={(event) => {
              event.preventDefault();
              apply({ q: query.trim() });
            }}
          >
            <TableFilterField search label="Search symbols, names or ISIN" htmlFor="instrument-q">
              <input
                id="instrument-q"
                type="search"
                maxLength={100}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </TableFilterField>
            <TableFilterField label="Exchange" htmlFor="instrument-exchange">
              <select
                id="instrument-exchange"
                value={filters.exchange}
                onChange={(event) =>
                  apply({
                    exchange: event.target.value as ExchangeInstrumentSearch["exchange"],
                    segment: "",
                    instrument_type: "",
                  })
                }
              >
                <option value="">All exchanges</option>
                <option value="NSE">NSE</option>
                <option value="BSE">BSE</option>
              </select>
            </TableFilterField>
            <TableFilterField label="Segment" htmlFor="instrument-segment">
              <select
                id="instrument-segment"
                value={filters.segment}
                onChange={(event) => apply({ segment: event.target.value })}
              >
                <option value="">All segments</option>
                {data.segments.map((segment) => (
                  <option key={segment}>{segment}</option>
                ))}
              </select>
            </TableFilterField>
            <TableFilterField label="Instrument type" htmlFor="instrument-type">
              <select
                id="instrument-type"
                value={filters.instrument_type}
                onChange={(event) => apply({ instrument_type: event.target.value })}
              >
                <option value="">All types</option>
                {data.instrument_types.map((type) => (
                  <option key={type}>{type}</option>
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
                onClick={() => {
                  setQuery("");
                  apply({
                    q: "",
                    exchange: "",
                    segment: "",
                    instrument_type: "",
                  });
                }}
              >
                Clear
              </Button>
            </Group>
          </TableFilters>
        }
        columns={[
          {
            id: "trading_symbol",
            label: "Symbol",
            value: (row) => row.trading_symbol,
            render: (row) => (
              <div className="table-primary">
                <strong>{row.trading_symbol}</strong>
                {row.company_id && (
                  <Text size="xs">
                    <Link to="/companies/$id/" params={{ id: String(row.company_id) }}>
                      {row.name}
                    </Link>
                  </Text>
                )}
              </div>
            ),
          },
          {
            id: "exchange",
            label: "Exchange / segment",
            value: (row) => `${row.exchange} ${row.segment}`,
            render: (row) => `${row.exchange} / ${row.segment}`,
          },
          {
            id: "instrument_type",
            label: "Type",
            value: (row) => row.instrument_type,
          },
          {
            id: "underlying",
            label: "Underlying / ISIN",
            value: (row) => row.underlying_symbol || row.isin,
            render: (row) => row.underlying_symbol || row.isin || "—",
            sortable: false,
          },
          {
            id: "expiry",
            label: "Expiry / strike",
            value: (row) => row.expiry,
            render: (row) =>
              row.expiry
                ? `${expiryDate.format(new Date(`${row.expiry}T00:00:00+05:30`))}${
                    row.strike_price === null
                      ? ""
                      : ` / ${row.strike_price.toLocaleString("en-IN")}`
                  }`
                : "—",
          },
          {
            id: "lot_size",
            label: "Lot size",
            value: (row) => row.lot_size,
            render: (row) => row.lot_size?.toLocaleString("en-IN") ?? "—",
            sortable: false,
          },
        ]}
        server={{
          page: data.page,
          pages: data.pages,
          total: data.total,
          pageSize: data.page_size,
          sort: filters.sort,
          onSort: (sort) => apply({ sort }),
          onPageSize: (page_size) => apply({ page_size }),
          paginationLabel: "Instrument pages",
          pageLink: (page, label) => (
            <Link to="/markets/instruments/" search={{ ...filters, page }}>
              {label}
            </Link>
          ),
        }}
        empty={<Text c="dimmed">No instruments match these filters.</Text>}
      />
    </Stack>
  );
}
