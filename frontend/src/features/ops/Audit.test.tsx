import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { OpsAuditEvent } from "../../shared/api/generated/types.gen";
import { auditSearchSchema } from "../../shared/api/ops";
import { session } from "../../test/session";

const events: OpsAuditEvent[] = [
  {
    id: 2,
    actor_name: "Deleted admin",
    action: "run job",
    target: "news.fetch",
    detail: "<img src=x onerror=alert(1)>",
    ip_address: "2001:db8::1",
    created_at: "2026-10-19T03:00:00Z",
  },
  {
    id: 1,
    actor_name: "member",
    action: "api token create",
    target: "",
    detail: "ke_12345678_\u2026\nOne-time secret is not retained",
    ip_address: null,
    created_at: "2026-10-18T03:00:00Z",
  },
];
const clients: QueryClient[] = [];
afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showAudit({
  staff = true,
  path = "/ops/audit/",
  status = 200,
  malformed = false,
  rows = events,
}: {
  staff?: boolean;
  path?: string;
  status?: number;
  malformed?: boolean;
  rows?: OpsAuditEvent[];
} = {}) {
  document.cookie = "csrftoken=audit-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  const fetchMock = vi.fn(async (input: string) => {
    const url = new URL(input, "http://localhost");
    const isSession = url.pathname.endsWith("/session");
    let body: unknown;
    if (isSession) body = { ...session, is_staff: staff, is_superuser: false };
    else if (status !== 200)
      body = {
        code: status === 403 ? "feature_not_available" : "failed",
        detail: "Audit unavailable.",
      };
    else if (malformed) body = {};
    else {
      const q = url.searchParams.get("q")?.toLowerCase() ?? "";
      const selected = rows.filter(
        (row) =>
          (!q ||
            [row.actor_name, row.action, row.target, row.detail, row.ip_address].some((value) =>
              value?.toLowerCase().includes(q),
            )) &&
          (!url.searchParams.get("actor") || row.actor_name === url.searchParams.get("actor")) &&
          (!url.searchParams.get("action") || row.action === url.searchParams.get("action")),
      );
      const size = Number(url.searchParams.get("page_size") ?? 10);
      const page = Number(url.searchParams.get("page") ?? 1);
      body = {
        items: selected.slice((page - 1) * size, page * size),
        page,
        page_size: size,
        pages: Math.max(1, Math.ceil(selected.length / size)),
        total: selected.length,
        actors: [...new Set(rows.map((row) => row.actor_name))],
        actions: [...new Set(rows.map((row) => row.action))],
      };
    }
    return new Response(JSON.stringify(body), {
      status: isSession ? 200 : status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
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
  return { router, client, fetchMock };
}

it("shows legacy audit fields, recorded actors, masked details, IPv6 and IST dates", async () => {
  await showAudit();
  expect(await screen.findByRole("heading", { level: 1, name: "Audit trail" })).toHaveFocus();
  expect(document.title).toBe("Audit trail | Kash Engine");
  expect(screen.getByRole("link", { name: "Audit trail", current: "page" })).toHaveAttribute(
    "href",
    "/ops/audit/",
  );
  const table = within(screen.getByRole("table", { name: "Audit trail" }));
  expect(table.getByRole("cell", { name: "Deleted admin" })).toBeInTheDocument();
  expect(table.getByRole("cell", { name: "api token create" })).toBeInTheDocument();
  expect(table.getByRole("cell", { name: "2001:db8::1" })).toBeInTheDocument();
  expect(table.getByText(/ke_12345678_/)).toBeInTheDocument();
  expect(table.getByText(/19 Oct 2026, 08:30:00 am IST/i)).toBeInTheDocument();
  expect(table.getByRole("cell", { name: "\u2013" })).toBeInTheDocument();
  expect(screen.getByText(events[0].detail)).toBeInTheDocument();
  expect(document.querySelector(".data-table img, .data-table script")).toBeNull();
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/ops/audit/");
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("rejects non-staff before fetching audit rows or advertising the navigation link", async () => {
  const { fetchMock } = await showAudit({ staff: false });
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Staff access required" })).toBeInTheDocument(),
  );
  expect(fetchMock.mock.calls.some(([url]) => url.includes("/ops/audit"))).toBe(false);
  expect(screen.queryByRole("link", { name: "Audit trail" })).not.toBeInTheDocument();
});

it("restores bookmarks, paginates on the server and retains filter/sort state", async () => {
  const { router, fetchMock } = await showAudit({
    path: "/ops/audit/?page=2&page_size=1&sort=-created_at",
  });
  expect(await screen.findByRole("heading", { name: "Audit trail" })).toBeInTheDocument();
  expect(document.title).toBe("Audit trail - page 2 | Kash Engine");
  expect(screen.queryByRole("cell", { name: "Deleted admin" })).not.toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "member" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "Previous" }));
  expect(await screen.findByRole("cell", { name: "Deleted admin" })).toBeInTheDocument();
  expect(router.state.location.search).toMatchObject({
    page: 1,
    page_size: 1,
    sort: "-created_at",
  });
  expect(
    fetchMock.mock.calls.some(
      ([url]) => url.includes("sort=-created_at") && url.includes("page_size=1"),
    ),
  ).toBe(true);
});

it("searches and changes exact filters, resetting pagination and preserving pending search", async () => {
  const { router, fetchMock } = await showAudit({ path: "/ops/audit/?page=2&page_size=1" });
  const input = await screen.findByRole("searchbox", { name: "Search audit records" });
  fireEvent.change(input, { target: { value: " news " } });
  fireEvent.change(screen.getByRole("combobox", { name: "Recorded admin" }), {
    target: { value: "Deleted admin" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page: 1,
      actor: "Deleted admin",
      q: "news",
    }),
  );
  expect(
    await screen.findByRole("cell", { name: "news.fetch <img src=x onerror=alert(1)>" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Action" }), {
    target: { value: "run job" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ action: "run job", q: "news" }),
  );
  expect(screen.getByRole("option", { name: "member" })).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([url]) =>
        url.includes("actor=Deleted+admin") &&
        url.includes("action=run+job") &&
        url.includes("q=news"),
    ),
  ).toBe(true);
  fireEvent.change(input, { target: { value: "absent" } });
  expect(await screen.findByText("No audit records match these filters.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ page: 1, actor: "", action: "", q: "" }),
  );
});

it("sends table sorting and page-size changes to the server", async () => {
  const { router } = await showAudit();
  const table = within(await screen.findByRole("table", { name: "Audit trail" }));
  fireEvent.click(table.getByRole("button", { name: "Admin" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ sort: "actor_name", page: 1 }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Audit trail" }), {
    target: { value: "25" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page_size: 25,
      sort: "actor_name",
      page: 1,
    }),
  );
  expect(screen.getByRole("columnheader", { name: "Admin" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
});

it("submits immediately and cancels pending search when clearing filters", async () => {
  const { router } = await showAudit();
  const input = await screen.findByRole("searchbox", { name: "Search audit records" });
  fireEvent.change(input, { target: { value: "news" } });
  fireEvent.submit(input.closest("form")!);
  await waitFor(() => expect(router.state.location.search).toMatchObject({ q: "news" }));
  fireEvent.change(input, { target: { value: "should not apply" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await new Promise((resolve) => setTimeout(resolve, 350));
  expect(router.state.location.search).toMatchObject({ q: "", actor: "", action: "", page: 1 });
});

it("keeps obsolete filter values visible for bookmark recovery", async () => {
  await showAudit({ path: "/ops/audit/?actor=old&action=obsolete" });
  expect(await screen.findByRole("combobox", { name: "Recorded admin" })).toHaveValue("old");
  expect(screen.getByRole("combobox", { name: "Action" })).toHaveValue("obsolete");
  expect(screen.getByText("No audit records match these filters.")).toBeInTheDocument();
});

it("renders empty history without inventing rows", async () => {
  await showAudit({ rows: [] });
  expect(await screen.findByText("No audit records match these filters.")).toBeInTheDocument();
  expect(screen.getByText("0 results")).toBeInTheDocument();
});

it("hides stale audit data after staff permission is revoked", async () => {
  const { client, fetchMock } = await showAudit();
  await screen.findByRole("table", { name: "Audit trail" });
  await waitFor(() => expect(client.isFetching()).toBe(0));
  fetchMock.mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        code: "feature_not_available",
        detail: "Staff access is required for Ops.",
      }),
      { status: 403, headers: { "Content-Type": "application/json" } },
    ),
  );
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["app", "ops", "audit"] });
  });
  expect(await screen.findByRole("heading", { name: "Staff access required" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
});

it("shows failed refresh explicitly and retries through the audit query", async () => {
  const { client, fetchMock } = await showAudit();
  await screen.findByRole("table", { name: "Audit trail" });
  await waitFor(() => expect(client.isFetching()).toBe(0));
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify({ code: "server_error", detail: "Audit unavailable." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    }),
  );
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["app", "ops", "audit"] });
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("Audit unavailable.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("table", { name: "Audit trail" })).toBeInTheDocument();
});

it.each([401, 403, 429, 500])("provides Audit recovery for HTTP %s", async (status) => {
  await showAudit({ status });
  expect(await screen.findByRole("alert")).toHaveTextContent("Audit unavailable.");
  expect(screen.getByRole("link", { name: "Back to Audit" })).toHaveAttribute(
    "href",
    "/ops/audit/",
  );
  if (status === 401)
    expect(screen.getByRole("link", { name: "Go to sign in" })).toBeInTheDocument();
});

it("rejects response contract drift visibly", async () => {
  await showAudit({ malformed: true });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The audit trail response does not match this app.",
  );
});

it.each([
  { sort: "detail" },
  { page_size: 101 },
  { q: "x".repeat(201) },
  { actor: "x".repeat(151) },
  { action: "x".repeat(51) },
])("rejects invalid bookmarked filters %j", (values) => {
  expect(auditSearchSchema.safeParse(values).success).toBe(false);
});
