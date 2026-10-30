import { Group, Pagination, Select, Table, Text } from "@mantine/core";
import { useMemo, useState } from "react";
import { LuArrowDown, LuArrowUp, LuArrowUpDown } from "react-icons/lu";
import type { ReactNode } from "react";

import { EmptyState, SkeletonRows } from "./States";

export type Column<Row> = {
  key: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  /** Value used for sorting; enables the sort button when present. */
  sortValue?: (row: Row) => string | number;
  align?: "left" | "right" | "center";
  width?: number | string;
  /** Hide below the md breakpoint (narrow screens). */
  hideOnMobile?: boolean;
};

type SortState = { key: string; dir: "asc" | "desc" } | null;

/**
 * Dense table with sticky header, client-side sort and pagination, and built-in empty/loading
 * states. Real data wiring will replace `rows` with server-paginated results later.
 */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
  selectedKey,
  toolbar,
  loading = false,
  empty,
  pageSize: initialPageSize = 10,
  pageSizes = [10, 25, 50],
  paginate = true,
  maxHeight,
  totalLabel = "rows",
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  onRowClick?: (row: Row) => void;
  selectedKey?: string | null;
  toolbar?: ReactNode;
  loading?: boolean;
  empty?: ReactNode;
  pageSize?: number;
  pageSizes?: number[];
  paginate?: boolean;
  maxHeight?: number;
  totalLabel?: string;
}) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  // Filters produce a new rows array; jump back to the first page when that happens.
  const [lastRows, setLastRows] = useState(rows);
  if (lastRows !== rows) {
    setLastRows(rows);
    setPage(1);
  }

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const get = column.sortValue;
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, columns, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pages);
  const visible = paginate ? sorted.slice((current - 1) * pageSize, current * pageSize) : sorted;

  const toggleSort = (key: string) => {
    setSort((prev) =>
      prev?.key !== key ? { key, dir: "desc" } : prev.dir === "desc" ? { key, dir: "asc" } : null,
    );
  };

  return (
    <div>
      {toolbar ? <div className="kv2-toolbar">{toolbar}</div> : null}
      {loading ? (
        <SkeletonRows rows={Math.min(pageSize, 8)} />
      ) : rows.length === 0 ? (
        (empty ?? (
          <EmptyState title="Nothing here yet" description="No rows match the current filters." />
        ))
      ) : (
        <div className="kv2-table-wrap" style={maxHeight ? { maxHeight } : undefined}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                {columns.map((column) => {
                  const active = sort?.key === column.key ? sort.dir : null;
                  return (
                    <Table.Th
                      key={column.key}
                      data-align={column.align}
                      w={column.width}
                      visibleFrom={column.hideOnMobile ? "md" : undefined}
                      aria-sort={
                        active === "asc"
                          ? "ascending"
                          : active === "desc"
                            ? "descending"
                            : undefined
                      }
                    >
                      {column.sortValue ? (
                        <button
                          type="button"
                          className="kv2-sort"
                          onClick={() => toggleSort(column.key)}
                        >
                          {column.header}
                          {active === "asc" ? (
                            <LuArrowUp size={12} />
                          ) : active === "desc" ? (
                            <LuArrowDown size={12} />
                          ) : (
                            <LuArrowUpDown size={12} opacity={0.5} />
                          )}
                        </button>
                      ) : (
                        column.header
                      )}
                    </Table.Th>
                  );
                })}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visible.map((row) => {
                const key = rowKey(row);
                return (
                  <Table.Tr
                    key={key}
                    data-selected={selectedKey === key}
                    data-clickable={Boolean(onRowClick)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                  >
                    {columns.map((column) => (
                      <Table.Td
                        key={column.key}
                        data-align={column.align}
                        visibleFrom={column.hideOnMobile ? "md" : undefined}
                      >
                        {column.render(row)}
                      </Table.Td>
                    ))}
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </div>
      )}
      {paginate && !loading && rows.length > 0 ? (
        <div className="kv2-table-footer">
          <Text size="xs" c="dimmed" className="kv2-num">
            {(current - 1) * pageSize + 1}–{Math.min(current * pageSize, sorted.length)} of{" "}
            {sorted.length.toLocaleString("en-IN")} {totalLabel}
          </Text>
          <Group gap={8}>
            <Select
              size="xs"
              w={96}
              aria-label="Rows per page"
              data={pageSizes.map((n) => ({ value: String(n), label: `${n} / page` }))}
              value={String(pageSize)}
              onChange={(value) => {
                setPageSize(Number(value));
                setPage(1);
              }}
            />
            <Pagination
              size="sm"
              total={pages}
              value={current}
              onChange={setPage}
              siblings={1}
              boundaries={1}
            />
          </Group>
        </div>
      ) : null}
    </div>
  );
}
