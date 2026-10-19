import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { ReportDetail, ReportPage } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const report: ReportDetail = {
  date: "2026-10-07",
  prediction: "up",
  strength: "7.3/10",
  text: "<script>alert('not HTML')</script>\nThe daily brief.",
  deliveries: [
    {
      id: 1,
      channel: "Telegram",
      status: "failed",
      status_label: "Failed",
      created_at: "2026-10-07T03:00:00Z",
      error: null,
    },
  ],
  older: "2026-10-05",
  newer: "2026-10-09",
};
const page: ReportPage = {
  items: [{ date: report.date, prediction: report.prediction, strength: report.strength }],
  page: 1,
  pages: 2,
  total: 2,
};
const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showReports({
  path = "/reports/",
  list = page,
  detail = report,
  status = 200,
  staff = false,
} = {}) {
  document.cookie = "csrftoken=reports-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const body =
        input === "/api/app/session"
          ? { ...session, is_staff: staff }
          : status !== 200
            ? {
                code:
                  status === 404
                    ? "not_found"
                    : status === 403
                      ? "feature_not_available"
                      : "server_error",
                detail: "Reports unavailable.",
              }
            : input.startsWith("/api/app/reports?")
              ? list
              : detail;
      return new Response(JSON.stringify(body), {
        status: input === "/api/app/session" ? 200 : status,
        headers: { "Content-Type": "application/json" },
      });
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

it("loads typed reports and links to real preview routes and the existing pages", async () => {
  await showReports();
  expect(await screen.findByRole("heading", { name: "Reports", level: 1 })).toBeInTheDocument();
  const link = screen.getByRole("link", { name: /Wednesday, 7 October 2026/ });
  expect(link).toHaveAttribute("href", "/reports/2026-10-07/");
  expect(screen.getByRole("cell", { name: "Up" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "7.3/10" })).toBeInTheDocument();
  expect(screen.getByText("7.3/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/reports/");
  expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute("href", "/reports/?page=2");
  expect(screen.queryByRole("link", { name: "Previous" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("aria-current", "page");
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("heading", { level: 1 })).not.toHaveAttribute("tabindex");
  expect(screen.getByText("7.3/10")).toHaveAttribute("data-tone", "positive");
});

it("keeps a lower-strength down outlook separate from strength color in report details", async () => {
  await showReports({
    path: "/reports/2026-10-07/",
    detail: { ...report, prediction: "down", strength: "6.3/10" },
  });
  expect(await screen.findByText("6.3/10")).toHaveAttribute("data-tone", "caution");
  expect(screen.getByText(/Down, strength/)).toHaveAttribute("data-tone", "down");
});

it("navigates to a report without leaving the React application", async () => {
  const router = await showReports();
  fireEvent.click(await screen.findByRole("link", { name: /Wednesday, 7 October 2026/ }));
  expect(await screen.findByRole("article", { name: "Report text" })).toHaveTextContent("<script>");
  await waitFor(() => expect(router.state.location.pathname).toBe("/reports/2026-10-07/"));
  expect(document.querySelector("article script")).toBeNull();
  expect(screen.getByRole("cell", { name: "Failed" })).toBeInTheDocument();
  expect(screen.getByText(/8:30 am IST/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Older:/ })).toHaveAttribute(
    "href",
    "/reports/2026-10-05/",
  );
  expect(screen.getByRole("link", { name: /Newer:/ })).toHaveAttribute(
    "href",
    "/reports/2026-10-09/",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("heading", { level: 1 })).not.toHaveAttribute("tabindex");
});

it("supports bookmarked pagination and omits out-of-range controls", async () => {
  await showReports({ path: "/reports/?page=2", list: { ...page, page: 2 } });
  expect(await screen.findByText("Page 2 of 2")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Previous" })).toHaveAttribute(
    "href",
    "/reports/?page=1",
  );
  expect(screen.queryByRole("link", { name: "Next" })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/app/reports?page=2", expect.anything());
});

it("searches and filters reports before paging and preserves server sorting", async () => {
  const router = await showReports({ path: "/reports/?page=2&sort=-strength&page_size=10" });
  const search = await screen.findByRole("searchbox", { name: "Search reports" });
  search.focus();
  fireEvent.change(search, { target: { value: "banks" } });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      q: "banks",
      page: 1,
      sort: "-strength",
      page_size: 10,
    }),
  );
  expect(search).toHaveFocus();
  fireEvent.change(screen.getByRole("combobox", { name: "Outlook" }), {
    target: { value: "down" },
  });
  await waitFor(() => expect(router.state.location.search.direction).toBe("down"));
  fireEvent.click(screen.getByRole("button", { name: "Report date" }));
  await waitFor(() => expect(router.state.location.search.sort).toBe("date"));
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Reports" }), {
    target: { value: "50" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page_size: 50,
      page: 1,
      direction: "down",
      q: "banks",
    }),
  );
});

it.each([false, true])("renders the empty state with staff hint = %s", async (staff) => {
  await showReports({ staff, list: { items: [], page: 1, pages: 1, total: 0 } });
  expect(await screen.findByText(/There is no report yet/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ops > Jobs" }) !== null).toBe(staff);
  expect(screen.queryByRole("navigation", { name: "Report pages" })).not.toBeInTheDocument();
});

it("supports direct detail loading and an unsent report", async () => {
  await showReports({
    path: "/reports/2026-10-07/",
    detail: { ...report, deliveries: [], older: null, newer: null, prediction: "", strength: null },
  });
  expect(await screen.findByText("This report was not sent.")).toBeInTheDocument();
  expect(screen.queryByText(/strength/)).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Older:/ })).not.toBeInTheDocument();
});

it.each([403, 404])(
  "shows a %s without nesting main landmarks or offering a useless retry",
  async (status) => {
    await showReports({ status });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      status === 404 ? "Report not found" : "Not on your account",
    );
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Reports" })).toHaveAttribute(
      "href",
      "/reports/",
    );
  },
);

it("rejects a broken report response instead of displaying invented data", async () => {
  await showReports({ list: { ...page, items: [{ ...page.items[0]!, date: "invalid" }] } });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The reports response does not match this app.",
  );
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

it("retries a failed Reports load successfully", async () => {
  await showReports({ status: 500 });
  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Unable to load this page" })).toBeInTheDocument();
  });
  vi.mocked(fetch).mockImplementation(
    async () =>
      new Response(JSON.stringify(page), {
        headers: { "Content-Type": "application/json" },
      }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Reports", level: 1 })).toBeInTheDocument();
});
