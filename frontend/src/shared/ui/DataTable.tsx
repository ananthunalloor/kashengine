import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { ColumnDef, PaginationState, SortingState } from "@tanstack/react-table";
import { useEffect, useId, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { TableFilterField, TableFilters } from "./TableFilters";
import {
  LuArrowDown,
  LuArrowUp,
  LuArrowUpDown,
  LuChevronLeft,
  LuChevronRight,
  LuChevronsLeft,
  LuChevronsRight,
  LuSearch,
  LuTable2,
} from "react-icons/lu";

export type TableColumn<T> = {
  id: string;
  label: string;
  value: (row: T) => string | number | null;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
};

type ServerTable = {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  sort?: string;
  onSort: (sort: string) => void;
  onPageSize: (size: number) => void;
  pageLink: (page: number, label: ReactNode) => ReactNode;
  paginationLabel: string;
};

export function DataTable<T>({
  data,
  columns,
  label,
  empty = "No results match. Try another search or clear the filters.",
  server,
  filters = [],
  initialSort = [],
  filterControls,
}: {
  data: T[];
  columns: TableColumn<T>[];
  label: string;
  empty?: ReactNode;
  server?: ServerTable;
  filters?: { label: string; value: (row: T) => string; options: string[] }[];
  initialSort?: SortingState;
  filterControls?: ReactNode;
}) {
  const tableId = useId();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [sorting, setSorting] = useState<SortingState>(initialSort);
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 10 });
  const visibleData = useMemo(
    () =>
      server
        ? data
        : data.filter((row) =>
            filters.every(
              (filter) => !selected[filter.label] || filter.value(row) === selected[filter.label],
            ),
          ),
    [data, server, filters, selected],
  );
  const definitions = useMemo<ColumnDef<T>[]>(
    () =>
      columns.map((column) => ({
        id: column.id,
        accessorFn: (row) => column.value(row) ?? undefined,
        header: column.label,
        enableSorting: column.sortable !== false,
        sortUndefined: "last",
      })),
    [columns],
  );
  const serverSorting = server?.sort
    ? [{ id: server.sort.replace(/^-/, ""), desc: server.sort.startsWith("-") }]
    : [];
  const table = useReactTable({
    data: visibleData,
    columns: definitions,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    manualPagination: !!server,
    manualSorting: !!server,
    manualFiltering: !!server,
    enableMultiSort: false,
    sortDescFirst: false,
    pageCount: server?.pages,
    state: {
      sorting: server ? serverSorting : sorting,
      globalFilter: search,
      pagination: server ? { pageIndex: server.page - 1, pageSize: server.pageSize } : pagination,
    },
    onSortingChange: (updater) => {
      const next =
        typeof updater === "function" ? updater(server ? serverSorting : sorting) : updater;
      if (server) server.onSort(next[0] ? `${next[0].desc ? "-" : ""}${next[0].id}` : "");
      else {
        setSorting(next);
        setPagination((value) => ({ ...value, pageIndex: 0 }));
      }
    },
    onPaginationChange: setPagination,
    onGlobalFilterChange: setSearch,
    globalFilterFn: "includesString",
    autoResetPageIndex: false,
  });
  const page = server?.page ?? pagination.pageIndex + 1;
  const pages = server?.pages ?? Math.max(1, table.getPageCount());
  const total = server?.total ?? table.getFilteredRowModel().rows.length;
  useEffect(() => {
    if (!server && pagination.pageIndex >= pages) {
      setPagination((value) => ({ ...value, pageIndex: pages - 1 }));
    }
  }, [pages, server, pagination.pageIndex]);
  const size = server?.pageSize ?? pagination.pageSize;
  const resetPage = () => setPagination((value) => ({ ...value, pageIndex: 0 }));
  function pageControl(target: number, name: string, icon: ReactNode, available: boolean) {
    const content = (
      <>
        <span aria-hidden="true">{icon}</span>
        <span className={name === "First page" || name === "Last page" ? "sr-only" : undefined}>
          {name}
        </span>
      </>
    );
    return available ? (
      server ? (
        server.pageLink(target, content)
      ) : (
        <button type="button" onClick={() => table.setPageIndex(target - 1)}>
          {content}
        </button>
      )
    ) : (
      <button type="button" disabled aria-label={name}>
        <span aria-hidden="true">{icon}</span>
      </button>
    );
  }
  return (
    <div className="data-panel">
      <div className="table-toolbar">
        <span className="table-label">
          <LuTable2 aria-hidden="true" />
          {label}
        </span>
        {server ? (
          filterControls
        ) : (
          <TableFilters onSubmit={(event) => event.preventDefault()}>
            <TableFilterField search label={`Search ${label}`} htmlFor={`${tableId}-search`}>
              <input
                id={`${tableId}-search`}
                type="search"
                aria-label={`Search ${label}`}
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  resetPage();
                }}
                placeholder="Search records..."
              />
            </TableFilterField>
            {filters.map((filter) => (
              <TableFilterField
                key={filter.label}
                label={filter.label}
                htmlFor={`${tableId}-${filter.label}`}
              >
                <select
                  id={`${tableId}-${filter.label}`}
                  aria-label={filter.label}
                  value={selected[filter.label] ?? ""}
                  onChange={(event) => {
                    setSelected((value) => ({ ...value, [filter.label]: event.target.value }));
                    resetPage();
                  }}
                >
                  <option value="">All {filter.label.toLowerCase()}</option>
                  {filter.options.map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              </TableFilterField>
            ))}
          </TableFilters>
        )}
        <label className="table-size">
          Rows per page
          <select
            aria-label={`Rows per page for ${label}`}
            value={size}
            onChange={(event) => {
              const value = Number(event.target.value);
              if (server) server.onPageSize(value);
              else {
                table.setPageSize(value);
                resetPage();
              }
            }}
          >
            {[...new Set([10, 25, 50, 100, size])]
              .sort((a, b) => a - b)
              .map((value) => (
                <option key={value}>{value}</option>
              ))}
          </select>
        </label>
      </div>
      <div
        className="table-scroll"
        role="region"
        aria-label={`${label} table, scroll horizontally for more columns`}
        tabIndex={0}
      >
        <table className="data-table">
          <caption className="sr-only">{label}</caption>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : undefined
                    }
                  >
                    {header.column.getCanSort() ? (
                      <button type="button" onClick={header.column.getToggleSortingHandler()}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" ? (
                          <LuArrowUp aria-hidden="true" />
                        ) : header.column.getIsSorted() === "desc" ? (
                          <LuArrowDown aria-hidden="true" />
                        ) : (
                          <LuArrowUpDown aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => {
                    const column = columns.find((column) => column.id === cell.column.id);
                    return (
                      <td key={cell.id}>
                        {column?.render
                          ? column.render(row.original)
                          : String(cell.getValue() ?? "\u2013")}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length}>
                  <div className="table-empty">
                    <LuSearch aria-hidden="true" />
                    {empty}
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="table-footer">
        <span role="status">
          {total
            ? `${(page - 1) * size + 1}-${Math.min(page * size, total)} of ${total} results`
            : "0 results"}
        </span>
        {pages > 1 && (
          <nav aria-label={server?.paginationLabel ?? `${label} pages`}>
            {pageControl(1, "First page", <LuChevronsLeft />, page > 1)}
            {pageControl(page - 1, "Previous", <LuChevronLeft />, page > 1)}
            <span>
              Page {page} of {pages}
            </span>
            {pageControl(page + 1, "Next", <LuChevronRight />, page < pages)}
            {pageControl(pages, "Last page", <LuChevronsRight />, page < pages)}
          </nav>
        )}
      </div>
    </div>
  );
}
