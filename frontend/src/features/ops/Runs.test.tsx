import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { OpsRunDetail, OpsRunSummary } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";
import { RunStatus } from "./Runs";

it.each([
  ["pending", "Waiting", "warning"],
  ["started", "Running", "neutral"],
  ["success", "Done", "positive"],
  ["failure", "Failed", "negative"],
] as const)("distinguishes %s runs with a semantic icon and label", (status, label, tone) => {
  render(<RunStatus run={{ status, status_label: label }} />);
  const badge = screen.getByText(label);
  expect(badge).toHaveClass(`ops-tone-${tone}`);
  expect(badge.querySelectorAll("svg")).toHaveLength(1);
  expect(badge.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
});

const pending: OpsRunSummary = {
  id: 1,
  label: "news.fetch",
  status: "pending",
  status_label: "Waiting",
  trigger: "manual",
  triggered_by: null,
  created_at: "2026-10-19T03:00:00Z",
  started_at: null,
  finished_at: null,
  duration_ms: null,
  duration: "\u2013",
  is_active: true,
};
const success: OpsRunSummary = {
  ...pending,
  id: 2,
  label: "reports.build",
  status: "success",
  status_label: "Done",
  trigger: "auto",
  started_at: pending.created_at,
  finished_at: "2026-10-19T03:00:01Z",
  duration_ms: 0,
  duration: "0 ms",
  is_active: false,
};
const detail: OpsRunDetail = {
  ...pending,
  task_id: "task-123",
  task_name: "apps.news.tasks.fetch",
  worker: "worker-one",
  args: "<b>Arguments</b>",
  result: "<script>Saved result</script>",
  error: "<img src=x onerror=alert(1)>",
  output: "Saved command output",
};
const clients: QueryClient[] = [];
afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  vi.useRealTimers();
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showRuns({
  staff = true,
  path = "/ops/runs/",
  status = 200,
  malformed = false,
  rows = [pending, success],
  run = detail,
}: {
  staff?: boolean;
  path?: string;
  status?: number;
  malformed?: boolean;
  rows?: OpsRunSummary[];
  run?: OpsRunDetail;
} = {}) {
  document.cookie = "csrftoken=ops-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  let detailStatus = status;
  let currentRun = run;
  const fetchMock = vi.fn(async (input: string) => {
    const url = new URL(input, "http://localhost");
    const isSession = url.pathname.endsWith("/session");
    const isDetail = /\/runs\/\d+$/.test(url.pathname);
    let body: unknown;
    const responseStatus = isSession ? 200 : isDetail ? detailStatus : status;
    if (isSession) body = { ...session, is_staff: staff, is_superuser: false };
    else if (responseStatus !== 200)
      body = {
        code: responseStatus === 403 ? "feature_not_available" : "failed",
        detail: "Ops history unavailable.",
      };
    else if (malformed) body = {};
    else if (isDetail) body = currentRun;
    else {
      const q = url.searchParams.get("q")?.toLowerCase() ?? "";
      const selected = rows.filter(
        (row) =>
          (!q || row.label.toLowerCase().includes(q)) &&
          (!url.searchParams.get("label") || row.label === url.searchParams.get("label")) &&
          (!url.searchParams.get("status") || row.status === url.searchParams.get("status")) &&
          (!url.searchParams.get("trigger") || row.trigger === url.searchParams.get("trigger")),
      );
      const size = Number(url.searchParams.get("page_size") ?? 10);
      const page = Number(url.searchParams.get("page") ?? 1);
      body = {
        items: selected.slice((page - 1) * size, page * size),
        page,
        pages: Math.max(1, Math.ceil(selected.length / size)),
        page_size: size,
        total: selected.length,
        labels: [...new Set(rows.map((row) => row.label))],
        retention_days: 45,
      };
    }
    return new Response(JSON.stringify(body), {
      status: responseStatus,
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
  const rendered = render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return {
    router,
    client,
    fetchMock,
    unmount: rendered.unmount,
    changeRun: (value: OpsRunDetail) => {
      currentRun = value;
    },
    failDetail: (value: number) => {
      detailStatus = value;
    },
  };
}

it.each(["/ops/runs/", "/ops/runs/1/"])(
  "blocks non-staff route %s before fetching data",
  async (path) => {
    const { fetchMock } = await showRuns({ staff: false, path });
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Staff access required" })).toBeInTheDocument(),
    );
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/ops/"))).toBe(false);
    expect(
      screen.queryByRole("link", { name: "Task runs", current: "page" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Task runs" })).toHaveAttribute(
      "href",
      "/ops/runs/",
    );
  },
);

it("hides previously loaded history after a staff-permission failure", async () => {
  const { client, fetchMock } = await showRuns();
  await screen.findByRole("link", { name: "news.fetch" });
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
    await client.invalidateQueries({ queryKey: ["app", "ops", "runs"] });
  });
  expect(await screen.findByRole("heading", { name: "Staff access required" })).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Task runs" })).not.toBeInTheDocument();
});

it("shows staff history, retention, missing times, zero duration, and semantic status colors", async () => {
  await showRuns();
  expect(await screen.findByRole("heading", { level: 1, name: "Task runs" })).not.toHaveAttribute(
    "tabindex",
  );
  expect(document.title).toBe("Task runs | Kash Engine");
  expect(screen.getByRole("link", { name: "Task runs", current: "page" })).toHaveAttribute(
    "href",
    "/ops/runs/",
  );
  expect(screen.getByText(/deleted after 45 days/)).toBeInTheDocument();
  expect(screen.getByText("An admin (deleted)")).toBeInTheDocument();
  expect(screen.getByText("Schedule or another task")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "0 ms" })).toBeInTheDocument();
  expect(screen.getByText("Waiting", { selector: "span" })).toHaveClass("ops-tone-warning");
  expect(screen.getByText("Done", { selector: "span" })).toHaveClass("ops-tone-positive");
  expect(screen.getAllByText(/19 Oct 2026, 08:30:00 am IST/i)).toHaveLength(2);
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("sends server search, exact filters, sorting and page size in bookmarked URL state", async () => {
  const { router, fetchMock } = await showRuns({ path: "/ops/runs/?page=2&page_size=1" });
  expect(await screen.findByRole("link", { name: "reports.build" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Result" }), {
    target: { value: "pending" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      page: 1,
      page_size: 1,
      status: "pending",
    }),
  );
  expect(await screen.findByRole("link", { name: "news.fetch" })).toBeInTheDocument();
  fireEvent.click(
    within(screen.getByRole("table", { name: "Task runs" })).getByRole("button", { name: "Time" }),
  );
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ page: 1, sort: "duration_ms" }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for Task runs" }), {
    target: { value: "25" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({ page: 1, page_size: 25 }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Job" }), {
    target: { value: "news.fetch" },
  });
  await waitFor(() => expect(router.state.location.search).toMatchObject({ label: "news.fetch" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Started by" }), {
    target: { value: "manual" },
  });
  await waitFor(() => expect(router.state.location.search).toMatchObject({ trigger: "manual" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search jobs, task IDs, or users" }), {
    target: { value: "missing" },
  });
  expect(await screen.findByText("No runs match these filters.")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([url]) =>
        url.includes("q=missing") &&
        url.includes("label=news.fetch") &&
        url.includes("status=pending") &&
        url.includes("trigger=manual") &&
        url.includes("sort=duration_ms"),
    ),
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      q: "",
      status: "",
      trigger: "",
      label: "",
      page: 1,
    }),
  );
});

it("paginates server results and navigates to details without leaving React", async () => {
  const { router } = await showRuns({ path: "/ops/runs/?page_size=1" });
  fireEvent.click(await screen.findByRole("link", { name: "Next" }));
  expect(await screen.findByRole("link", { name: "reports.build" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/ops/runs/");
  fireEvent.click(screen.getByRole("link", { name: "reports.build" }));
  expect(await screen.findByRole("heading", { level: 1, name: "news.fetch" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/ops/runs/2/");
});

it("renders stored diagnostics only as text, metadata and pending guidance", async () => {
  await showRuns({ path: "/ops/runs/1/" });
  expect(await screen.findByRole("heading", { name: "news.fetch", level: 1 })).not.toHaveAttribute(
    "tabindex",
  );
  expect(screen.getByText(detail.args)).toBeInTheDocument();
  expect(screen.getByText(detail.result)).toBeInTheDocument();
  expect(screen.getByText(detail.error)).toBeInTheDocument();
  expect(screen.getByText(detail.output)).toBeInTheDocument();
  expect(screen.getByText("task-123")).toBeInTheDocument();
  expect(screen.getByText("worker-one")).toBeInTheDocument();
  expect(screen.getByText(/job waits for a worker/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ops Overview" })).toHaveAttribute("href", "/ops/");
  expect(document.querySelector("pre img, pre script, dd b")).toBeNull();
  expect(screen.getAllByText("\u2013").length).toBeGreaterThan(1);
});

it("polls active runs every three seconds, stops at completion, and supports manual refresh", async () => {
  const { fetchMock, changeRun } = await showRuns({ path: "/ops/runs/1/" });
  await screen.findByRole("heading", { name: "news.fetch" });
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  // Recreate the observer interval under the controlled clock.
  fireEvent.click(await screen.findByRole("button", { name: "Refresh now" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh now" })).toBeEnabled());
  const before = fetchMock.mock.calls.length;
  changeRun({ ...detail, status: "success", status_label: "Done", is_active: false });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  await waitFor(() => expect(screen.getByText("Done")).toBeInTheDocument());
  expect(fetchMock.mock.calls.length).toBe(before + 1);
  const after = fetchMock.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(fetchMock.mock.calls.length).toBe(after);
  expect(screen.queryByText(/refreshes every 3 seconds/)).not.toBeInTheDocument();
});

it("hides cached diagnostics and stops polling when staff access is revoked", async () => {
  const { failDetail, fetchMock } = await showRuns({ path: "/ops/runs/1/" });
  await screen.findByText(detail.output);
  failDetail(403);
  fireEvent.click(await screen.findByRole("button", { name: "Refresh now" }));
  expect(await screen.findByRole("heading", { name: "Staff access required" })).toBeInTheDocument();
  expect(screen.queryByText(detail.output)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  const after = fetchMock.mock.calls.length;
  await new Promise((resolve) => setTimeout(resolve, 3200));
  expect(fetchMock.mock.calls.length).toBe(after);
});

it("reports background refresh errors explicitly and allows recovery without stale diagnostics", async () => {
  const { failDetail } = await showRuns({ path: "/ops/runs/1/" });
  await screen.findByText(detail.output);
  failDetail(500);
  fireEvent.click(await screen.findByRole("button", { name: "Refresh now" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Ops history unavailable.");
  expect(screen.queryByText(detail.output)).not.toBeInTheDocument();
  failDetail(200);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText(detail.output)).toBeInTheDocument();
});

it.each([401, 403, 404, 429, 500])(
  "shows task-specific error recovery for status %s",
  async (status) => {
    await showRuns({ status });
    expect(await screen.findByRole("alert")).toHaveTextContent("Ops history unavailable.");
    expect(screen.getByRole("link", { name: "Back to Task runs" })).toHaveAttribute(
      "href",
      "/ops/runs/",
    );
    expect(screen.queryByRole("table", { name: "Task runs" })).not.toBeInTheDocument();
    if (status === 401)
      expect(screen.getByRole("link", { name: "Go to sign in" })).toBeInTheDocument();
  },
);

it.each(["/ops/runs/", "/ops/runs/1/"])("rejects malformed response on %s", async (path) => {
  await showRuns({ path, malformed: true });
  expect(await screen.findByRole("alert")).toHaveTextContent(/response does not match this app/);
});
