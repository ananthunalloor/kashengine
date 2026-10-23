import { Alert, Anchor, Button, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import type { CompanyMarketPage, CompanyMarketItem } from "../../shared/api/generated/types.gen";
import type { CompanyMarketSearch } from "../../shared/api/companies";
import { DataTable } from "../../shared/ui/DataTable";
import type { TableColumn } from "../../shared/ui/DataTable";
import { TableFilterField, TableFilters } from "../../shared/ui/TableFilters";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { QuoteFreshness } from "../companies/Company";

export function CompanyMarkets({
  data,
  filters,
  onFilter,
  canViewCompanies,
}: {
  data: CompanyMarketPage;
  filters: CompanyMarketSearch;
  onFilter: (filters: CompanyMarketSearch) => void;
  canViewCompanies: boolean;
}) {
  usePageTitle("Company market data");
  const [q, setQ] = useState(filters.q);
  return (
    <Stack gap="xl">
      <header>
        <Anchor component={Link} to="/markets/">
          Markets and predictions
        </Anchor>
        <Title order={1}>Company market data</Title>
        <Text c="dimmed">
          Saved Upstox observations for the company directory. Stream workers save up to once every
          five seconds; scheduled snapshots run every five minutes during trading sessions. These
          pages never call external providers.
        </Text>
      </header>
      {!data.upstox_enabled && (
        <Alert color="orange" title="Upstox ingestion is disabled">
          Previously saved observations remain available. Staff can configure Upstox in Ops
          settings.
        </Alert>
      )}
      <DataTable
        data={data.items}
        label="Company market data"
        filterControls={
          <TableFilters
            onSubmit={(event) => {
              event.preventDefault();
              onFilter({ ...filters, q: q.trim(), page: 1 });
            }}
          >
            <TableFilterField search label="Company name or symbol" htmlFor="market-company-query">
              <input
                id="market-company-query"
                type="search"
                value={q}
                maxLength={100}
                onChange={(event) => setQ(event.target.value)}
              />
            </TableFilterField>
            <Button type="submit">Search</Button>
          </TableFilters>
        }
        columns={(
          [
            {
              id: "name",
              label: "Company",
              value: (row) => row.name,
              render: (row) =>
                canViewCompanies ? (
                  <Link to="/companies/$id/" params={{ id: String(row.id) }}>
                    {row.name}
                  </Link>
                ) : (
                  row.name
                ),
            },
            { id: "symbol", label: "Symbol", value: (row) => row.symbol },
            {
              id: "price",
              label: "Price (INR)",
              value: (row) => row.quote?.price ?? null,
              render: (row) =>
                row.quote?.price.toLocaleString("en-IN", { maximumFractionDigits: 2 }) ??
                "No saved quote",
            },
            {
              id: "change",
              label: "Change (%)",
              value: (row) => row.quote?.change_pct ?? null,
              render: (row) => row.quote?.change_pct?.toFixed(2) ?? "Not available",
            },
            {
              id: "as_of",
              label: "Source and time",
              value: (row) => row.quote?.as_of ?? null,
              render: (row) => (row.quote ? <QuoteFreshness quote={row.quote} /> : "Not fetched"),
            },
            {
              id: "error",
              label: "Refresh status",
              value: (row) => row.error,
              render: (row) => row.error || "No recorded error",
            },
          ] satisfies TableColumn<CompanyMarketItem>[]
        ).map((column) => ({ ...column, sortable: false }))}
        server={{
          page: data.page,
          pages: data.pages,
          total: data.total,
          pageSize: data.page_size,
          onSort: () => {},
          onPageSize: (page_size) => onFilter({ ...filters, page_size, page: 1 }),
          paginationLabel: "Company market pages",
          pageLink: (page, label) => (
            <Link to="/markets/live/" search={{ ...filters, page }}>
              {label}
            </Link>
          ),
        }}
        empty={<Text c="dimmed">No saved company matches this search.</Text>}
      />
    </Stack>
  );
}
