import { fireEvent, render, screen, within } from "@testing-library/react";
import type { FormEvent } from "react";
import { expect, it, vi } from "vitest";

import { DataTable } from "./DataTable";
import { displayNumber } from "./displayNumber";
import { TableFilterField, TableFilters } from "./TableFilters";

const data = Array.from({ length: 26 }, (_, index) => ({
  name: `Record ${String(index + 1).padStart(2, "0")}`,
  score: index + 1,
  status: index % 2 ? "Failed" : "Sent",
}));
const columns = [
  { id: "name", label: "Name", value: (row: (typeof data)[number]) => row.name },
  { id: "score", label: "Score", value: (row: (typeof data)[number]) => row.score },
  { id: "status", label: "Status", value: (row: (typeof data)[number]) => row.status },
];

it("pins only opted-in column headers and cells and leaves the empty state unpinned", () => {
  const stickyColumns = [
    ...columns,
    {
      id: "actions",
      label: "Actions",
      value: () => null,
      sortable: false,
      stickyRight: true,
      render: () => <button type="button">Edit record</button>,
    },
  ];
  render(<DataTable data={data.slice(0, 2)} columns={stickyColumns} label="Records" />);
  expect(screen.getByRole("columnheader", { name: "Actions" })).toHaveClass("table-sticky-right");
  expect(screen.getByRole("columnheader", { name: "Name" })).not.toHaveClass("table-sticky-right");
  for (const button of screen.getAllByRole("button", { name: "Edit record" })) {
    expect(button.closest("td")).toHaveClass("table-sticky-right");
  }
  expect(screen.getByRole("cell", { name: "Record 01" })).not.toHaveClass("table-sticky-right");
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no matches" } });
  expect(screen.getByRole("cell")).not.toHaveClass("table-sticky-right");
});

it("paginates, sorts numerically, filters all rows, and resets page on search/size change", () => {
  render(
    <DataTable
      data={data}
      columns={columns}
      label="Records"
      filters={[{ label: "Status", value: (row) => row.status, options: ["Sent", "Failed"] }]}
    />,
  );
  expect(screen.getAllByRole("row")).toHaveLength(11);
  fireEvent.click(screen.getByRole("button", { name: "Last page" }));
  expect(screen.getByText("Record 26")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Record 02" } });
  expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getByText("Record 02")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "Sent" } });
  expect(screen.getByText("1-10 of 13 results")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Records" }), {
    target: { value: "25" },
  });
  expect(screen.getAllByRole("row")).toHaveLength(14);
  fireEvent.click(screen.getByRole("button", { name: "Score" }));
  const heading = screen.getByRole("columnheader", { name: "Score" });
  expect(heading).toHaveAttribute("aria-sort");
  expect(
    within(screen.getAllByRole("row")[1]!).getByRole("cell", { name: "1" }),
  ).toBeInTheDocument();
});

it("shows a useful empty filtered state and keeps the search focused", () => {
  render(<DataTable data={data} columns={columns} label="Records" />);
  const search = screen.getByRole("searchbox");
  search.focus();
  fireEvent.change(search, { target: { value: "does not exist" } });
  expect(screen.getByText(/No results match/)).toBeInTheDocument();
  expect(screen.getByText("0 results")).toBeInTheDocument();
  expect(search).toHaveFocus();
});

it("uses server sort/size callbacks without re-sorting or slicing a page locally", () => {
  const onSort = vi.fn(),
    onPageSize = vi.fn();
  render(
    <DataTable
      data={data.slice(0, 2)}
      columns={columns}
      label="Records"
      server={{
        page: 2,
        pages: 13,
        total: 26,
        pageSize: 2,
        sort: "name",
        onSort,
        onPageSize,
        paginationLabel: "Record pages",
        pageLink: (page, label) => <a href={`?page=${page}`}>{label}</a>,
      }}
    />,
  );
  expect(screen.getAllByRole("row")).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: "Name" }));
  expect(onSort).toHaveBeenCalledWith("-name");
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Records" }), {
    target: { value: "50" },
  });
  expect(onPageSize).toHaveBeenCalledWith(50);
  expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute("href", "?page=3");
  expect(screen.getByText("Record 01")).toBeInTheDocument();
});

it("keeps nulls last and parses formatted numeric values without sorting lexically", () => {
  expect(displayNumber("−1.25%")).toBe(-1.25);
  expect(displayNumber("10.0/10")).toBe(10);
  expect(displayNumber("1,234.50")).toBe(1234.5);
  expect(displayNumber("–")).toBeNull();
  render(
    <DataTable
      data={[{ n: null }, { n: 10 }, { n: 2 }]}
      label="Numbers"
      columns={[{ id: "n", label: "Number", value: (row) => row.n }]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Number" }));
  expect(screen.getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["2", "10", "–"]);
});

it("places server filters in the same toolbar as local filters without adding a local search", () => {
  const onSubmit = vi.fn((event: FormEvent<HTMLFormElement>) => event.preventDefault());
  render(
    <DataTable
      data={data.slice(0, 2)}
      columns={columns}
      label="Records"
      filterControls={
        <TableFilters onSubmit={onSubmit}>
          <TableFilterField search label="Search records on the server" htmlFor="server-search">
            <input id="server-search" type="search" />
          </TableFilterField>
          <TableFilterField label="Status" htmlFor="server-status">
            <select id="server-status">
              <option>All statuses</option>
            </select>
          </TableFilterField>
        </TableFilters>
      }
      server={{
        page: 2,
        pages: 3,
        total: 6,
        pageSize: 2,
        onSort: vi.fn(),
        onPageSize: vi.fn(),
        paginationLabel: "Record pages",
        pageLink: (page, label) => <a href={`?page=${page}`}>{label}</a>,
      }}
    />,
  );
  const search = screen.getByRole("searchbox", { name: "Search records on the server" });
  const toolbar = search.closest(".table-toolbar");
  expect(toolbar).toContainElement(screen.getByRole("combobox", { name: "Status" }));
  expect(toolbar).toContainElement(
    screen.getByRole("combobox", { name: "Rows per page for Records" }),
  );
  expect(search.closest(".table-search")?.querySelector("svg")).not.toBeNull();
  expect(screen.getAllByRole("searchbox")).toHaveLength(1);
  fireEvent.submit(search.closest("form")!);
  expect(onSubmit).toHaveBeenCalledOnce();
  expect(screen.getByText("3-4 of 6 results")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "First page" }).lastElementChild).toHaveClass("sr-only");
  expect(screen.getByRole("link", { name: "Last page" }).lastElementChild).toHaveClass("sr-only");
});

it("uses the same compact pagination labels for local buttons as server links", () => {
  render(<DataTable data={data} columns={columns} label="Records" />);
  expect(screen.getByRole("button", { name: "First page" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Last page" }).lastElementChild).toHaveClass("sr-only");
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("button", { name: "First page" }).lastElementChild).toHaveClass(
    "sr-only",
  );
  expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
  expect(screen.getByText("11-20 of 26 results")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Last page" }));
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Last page" })).toBeDisabled();
});
