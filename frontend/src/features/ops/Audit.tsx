import { Button, Group, Stack, Text, Title } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { LuClipboardList, LuSearch, LuX } from "react-icons/lu";

import type { OpsAuditPage } from "../../shared/api/generated/types.gen";
import type { AuditSearch } from "../../shared/api/ops";
import { DataTable } from "../../shared/ui/DataTable";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { OpsTime } from "./OpsTime";
import { TableFilterField, TableFilters } from "../../shared/ui/TableFilters";

export function Audit({
  data,
  filters,
  onFilter,
}: {
  data: OpsAuditPage;
  filters: AuditSearch;
  onFilter: (filters: AuditSearch, replace?: boolean) => void;
}) {
  usePageTitle(`Audit trail${data.page > 1 ? ` - page ${data.page}` : ""}`);
  const [query, setQuery] = useState(filters.q);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const searchInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setQuery(filters.q);
    return () => clearTimeout(timer.current);
  }, [filters.q, filters.actor, filters.action, filters.page, filters.page_size, filters.sort]);

  function change(values: AuditSearch, replace = false) {
    clearTimeout(timer.current);
    onFilter({ ...values, q: query.trim(), page: 1 }, replace);
  }

  const filterControls = (
    <TableFilters
      onSubmit={(event) => {
        event.preventDefault();
        change(filters);
      }}
    >
      <TableFilterField search label="Search audit records" htmlFor="audit-query">
        <input
          id="audit-query"
          type="search"
          maxLength={200}
          autoComplete="off"
          ref={searchInput}
          value={query}
          placeholder="Admin, action, target, detail, or address"
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
            clearTimeout(timer.current);
            timer.current = setTimeout(
              () => onFilter({ ...filters, q: value.trim(), page: 1 }, true),
              300,
            );
          }}
        />
      </TableFilterField>
      <TableFilterField label="Recorded admin" htmlFor="audit-actor">
        <select
          id="audit-actor"
          value={filters.actor}
          onChange={(event) => change({ ...filters, actor: event.target.value })}
        >
          <option value="">All admins</option>
          {filters.actor && !data.actors.includes(filters.actor) && (
            <option>{filters.actor}</option>
          )}
          {data.actors.map((actor) => (
            <option key={actor}>{actor}</option>
          ))}
        </select>
      </TableFilterField>
      <TableFilterField label="Action" htmlFor="audit-action">
        <select
          id="audit-action"
          value={filters.action}
          onChange={(event) => change({ ...filters, action: event.target.value })}
        >
          <option value="">All actions</option>
          {filters.action && !data.actions.includes(filters.action) && (
            <option>{filters.action}</option>
          )}
          {data.actions.map((action) => (
            <option key={action}>{action}</option>
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
            clearTimeout(timer.current);
            setQuery("");
            onFilter({ ...filters, q: "", actor: "", action: "", page: 1 });
            searchInput.current?.focus();
          }}
        >
          Clear filters
        </Button>
      </Group>
    </TableFilters>
  );
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="xs">
          <LuClipboardList aria-hidden="true" /> Operations / recorded activity
        </Text>
        <Title order={1} className="ops-page-title">
          <LuClipboardList aria-hidden="true" /> Audit trail
        </Title>
        <Text c="dimmed" mt="sm">
          Recorded actions: jobs started, sessions ended, account changes, and API token management.
          Names are preserved as recorded, even after an account is renamed or deleted.
        </Text>
      </header>
      <DataTable
        data={data.items}
        label="Audit trail"
        filterControls={filterControls}
        empty="No audit records match these filters."
        columns={[
          {
            id: "created_at",
            label: "Time",
            value: (event) => event.created_at,
            render: (event) => <OpsTime value={event.created_at} />,
          },
          {
            id: "actor_name",
            label: "Admin",
            value: (event) => event.actor_name,
            render: (event) => event.actor_name || "Not recorded",
          },
          { id: "action", label: "Action", value: (event) => event.action },
          {
            id: "target",
            label: "Target",
            value: (event) => event.target,
            render: (event) => (
              <div className="table-story">
                <span>{event.target || "\u2013"}</span>
                {event.detail && (
                  <Text size="sm" c="dimmed" mt="xs" className="audit-detail">
                    {event.detail}
                  </Text>
                )}
              </div>
            ),
          },
          {
            id: "ip_address",
            label: "Address",
            value: (event) => event.ip_address,
            render: (event) => event.ip_address || "\u2013",
          },
        ]}
        server={{
          page: data.page,
          pages: data.pages,
          total: data.total,
          pageSize: data.page_size,
          sort: filters.sort,
          onSort: (sort) => change({ ...filters, sort }),
          onPageSize: (page_size) => change({ ...filters, page_size }),
          paginationLabel: "Audit history pages",
          pageLink: (page, label) => (
            <Link to="/ops/audit/" search={{ ...filters, page }}>
              {label}
            </Link>
          ),
        }}
      />
    </Stack>
  );
}
