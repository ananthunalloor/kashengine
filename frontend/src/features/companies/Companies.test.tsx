import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { CompanyPage } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const data: CompanyPage = {
  items: [
    {
      id: 1,
      name: "<b>Alpha Bank</b>",
      symbol: "ALPHA",
      listings: [
        { exchange: "NSE", symbol: "ALPHA", instrument_key: "NSE_EQ|INE000A01001" },
        { exchange: "BSE", symbol: "500001", instrument_key: "BSE_EQ|INE000A01001" },
      ],
      sector: "Finance",
      screener_url: "https://www.screener.in/company/ALPHA/",
      last_updated: "2026-10-16T23:00:00Z",
    },
    {
      id: 2,
      name: "Beta Tools",
      symbol: "BETA",
      listings: [],
      sector: "",
      screener_url: "javascript:alert(1)",
      last_updated: null,
    },
  ],
  page: 1,
  pages: 3,
  total: 5,
  indices: [{ value: "NIFTY_50", label: "Nifty 50", count: 50 }],
};
const clients: QueryClient[] = [];
afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showCompanies({
  path = "/companies/",
  body = data,
  status = 200,
  staff = false,
}: { path?: string; body?: unknown; status?: number; staff?: boolean } = {}) {
  document.cookie = "csrftoken=companies-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const isSession = input === "/api/app/session";
      return new Response(
        JSON.stringify(
          isSession
            ? {
                ...session,
                is_staff: staff,
                features: [...session.features, "companies"],
                navigation: [...session.navigation, { label: "Companies", url: "/companies/" }],
              }
            : body,
        ),
        { status: isSession ? 200 : status, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/",
    trailingSlash: "always",
    history: createMemoryHistory({ initialEntries: [path] }),
    context: { queryClient: client },
    defaultPendingMinMs: 0,
  });
  await router.load();
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return router;
}

it("shows directory fields, safe source links, IST dates and preview navigation", async () => {
  await showCompanies();
  expect(await screen.findByRole("heading", { level: 1, name: "Companies" })).not.toHaveAttribute(
    "tabindex",
  );
  expect(document.title).toBe("Companies | Kash Engine");
  expect(screen.getByRole("link", { name: /<b>Alpha Bank<\/b>/ })).toHaveAttribute(
    "href",
    "/companies/1/",
  );
  const source = screen.getByRole("link", { name: /Screener source/ });
  expect(source).toHaveAttribute("href", data.items[0].screener_url);
  expect(source).toHaveAttribute("rel", "noopener noreferrer");
  expect(source).toHaveAttribute("target", "_blank");
  expect(document.querySelector(".data-table b")).toBeNull();
  expect(screen.getByRole("link", { name: /Beta Tools/ })).toHaveAttribute("href", "/companies/2/");
  expect(screen.getByText("Source link unavailable.")).toBeInTheDocument();
  expect(screen.getByText("17 Oct 2026")).toBeInTheDocument();
  expect(screen.getByText("Not fetched")).toBeInTheDocument();
  expect(screen.getByText("Not available")).toBeInTheDocument();
  expect(screen.getByText("NSE")).toBeInTheDocument();
  expect(screen.getByText("500001")).toBeInTheDocument();
  expect(screen.getByText("Not imported")).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Nifty index" })).toHaveValue("NIFTY_50");
  expect(screen.getByRole("combobox", { name: "Nifty index" })).toHaveTextContent("Nifty 50 (50)");
  expect(screen.getByText("5 companies")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/companies/");
  expect(screen.getByRole("link", { name: "Companies", current: "page" })).toHaveAttribute(
    "href",
    "/companies/",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("filters and bookmarks companies by Nifty index", async () => {
  const router = await showCompanies();

  fireEvent.change(await screen.findByRole("combobox", { name: "Nifty index" }), {
    target: { value: "NIFTY_50" },
  });

  await waitFor(() => expect(router.state.location.search.index).toBe("NIFTY_50"));
  expect(fetch).toHaveBeenCalledWith(
    "/api/app/companies?q=&page=1&index=NIFTY_50",
    expect.anything(),
  );
});

it("allows switching from the default Nifty 50 to all companies", async () => {
  const router = await showCompanies();

  fireEvent.change(await screen.findByRole("combobox", { name: "Nifty index" }), {
    target: { value: "" },
  });

  await waitFor(() => expect(router.state.location.search.index).toBe(""));
  expect(fetch).toHaveBeenCalledWith("/api/app/companies?q=&page=1", expect.anything());
});

it("restores bookmarked search, debounces typing, resets page and keeps focus", async () => {
  const router = await showCompanies({ path: "/companies/?q=bank&page=2" });
  const input = await screen.findByRole("searchbox");
  expect(input.closest(".table-toolbar")).toContainElement(
    screen.getByRole("combobox", { name: "Sector" }),
  );
  expect(input).toHaveValue("bank");
  input.focus();
  fireEvent.change(input, { target: { value: " tools " } });
  expect(router.state.location.search).toMatchObject({ q: "bank", page: 2 });
  await waitFor(() => expect(router.state.location.search).toMatchObject({ q: "tools", page: 1 }));
  expect(input).toHaveFocus();
  expect(fetch).toHaveBeenCalledWith(
    "/api/app/companies?q=tools&page=1&index=NIFTY_50",
    expect.anything(),
  );
});

it("submits immediately and cancels pending typing on clear", async () => {
  const router = await showCompanies();
  const input = await screen.findByRole("searchbox");
  fireEvent.change(input, { target: { value: "alpha" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => expect(router.state.location.search.q).toBe("alpha"));
  fireEvent.change(input, { target: { value: "pending" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  await waitFor(() => expect(router.state.location.search.q).toBe(""));
  await new Promise((resolve) => setTimeout(resolve, 350));
  expect(router.state.location.search.q).toBe("");
  expect(input).toHaveValue("");
  expect(input).toHaveFocus();
});

it("preserves search while paging and restores it on back navigation", async () => {
  const router = await showCompanies({
    path: "/companies/?q=bank&page=2",
    body: { ...data, page: 2 },
  });
  const next = await screen.findByRole("link", { name: "Next" });
  expect(next).toHaveAttribute("href", "/companies/?q=bank&page=3&index=NIFTY_50");
  fireEvent.click(next);
  await waitFor(() => expect(router.state.location.search).toMatchObject({ q: "bank", page: 3 }));
  router.history.back();
  await waitFor(() => expect(router.state.location.search).toMatchObject({ q: "bank", page: 2 }));
  expect(screen.getByRole("searchbox")).toHaveValue("bank");
});

it.each([false, true])(
  "limits import guidance to staff on unfiltered empty directory (%s)",
  async (staff) => {
    await showCompanies({ staff, body: { items: [], total: 0, page: 1, pages: 1 } });
    expect(await screen.findByText(/No company matches/)).toBeInTheDocument();
    expect(screen.queryByText("python manage.py import_companies") !== null).toBe(staff);
    expect(screen.queryByRole("navigation", { name: "Company pages" })).not.toBeInTheDocument();
  },
);

it("hides import guidance for a filtered empty result", async () => {
  await showCompanies({
    staff: true,
    path: "/companies/?q=unmatched",
    body: { items: [], total: 0, page: 1, pages: 1 },
  });
  expect(await screen.findByText(/No company matches/)).toBeInTheDocument();
  expect(screen.queryByText("python manage.py import_companies")).not.toBeInTheDocument();
});

it.each([401, 403])("handles %s access errors within the shell", async (status) => {
  await showCompanies({
    status,
    body: {
      code: status === 401 ? "unauthenticated" : "feature_not_available",
      detail: "Companies unavailable.",
    },
  });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      status === 401 ? "Sign in to continue" : "Not on your account",
    ),
  );
  expect(screen.getByRole("link", { name: "Back to Companies" })).toHaveAttribute(
    "href",
    "/companies/",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("surfaces malformed responses and retries successfully", async () => {
  await showCompanies({ body: { items: [{}] } });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("does not match this app"),
  );
  vi.mocked(fetch).mockImplementation(
    async () =>
      new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("5 companies")).toBeInTheDocument();
});

it("sends server sorting, page size and exact sector filters and restores them from the URL", async () => {
  const router = await showCompanies({
    path: "/companies/?q=bank&page=2&sort=-symbol&page_size=10&sector=Finance",
    body: { ...data, page_size: 10, sectors: ["Finance", "Tools"] },
  });
  expect(await screen.findByRole("columnheader", { name: "Symbol" })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  expect(screen.getByRole("combobox", { name: "Sector" })).toHaveValue("Finance");
  fireEvent.click(screen.getByRole("button", { name: "Company" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      sort: "name",
      page: 1,
      page_size: 10,
      sector: "Finance",
    }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Companies" }), {
    target: { value: "50" },
  });
  await waitFor(() => expect(router.state.location.search.page_size).toBe(50));
  fireEvent.change(screen.getByRole("combobox", { name: "Sector" }), {
    target: { value: "Tools" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      q: "bank",
      sort: "name",
      sector: "Tools",
      page_size: 50,
      page: 1,
    }),
  );
});
