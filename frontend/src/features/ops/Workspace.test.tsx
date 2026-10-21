import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import { zOpsForm, zOpsPage } from "../../shared/api/generated/zod.gen";
import { opsSearchSchema, submitOpsForm } from "../../shared/api/opsWorkspace";
import { session } from "../../test/session";
import { OpsActionForm } from "./Workspace";

const clients: QueryClient[] = [];
afterEach(() => {
  clients.forEach((client) => client.clear());
  clients.length = 0;
  document.cookie = "csrftoken=; Max-Age=0; path=/";
});

const form = zOpsForm.parse({
  id: "feeds/",
  action: "/api/app/ops/actions/feeds/",
  label: "Add feed",
  fields: [
    { name: "name", label: "Feed name", required: true },
    { name: "url", label: "Feed URL", required: true },
  ],
});
const page = zOpsPage.parse({
  title: "News feeds",
  description: "Existing backend validation, new React controls.",
  sections: [
    {
      title: "Feeds",
      forms: [form],
      table: {
        server: true,
        page: 1,
        pages: 3,
        page_size: 10,
        total: 25,
        columns: [
          { label: "Name", key: "name" },
          { label: "State", key: "state" },
        ],
        filters: ["state"],
        filter_choices: { state: ["On", "Off"] },
        rows: [
          {
            cells: { name: { text: "<b>Saved feed</b>" }, state: { text: "On", tone: "positive" } },
          },
        ],
      },
    },
  ],
});

async function show({
  path = "/ops/feeds/",
  staff = true,
  superuser = true,
  status = 200,
  body: content = page,
} = {}) {
  document.cookie = "csrftoken=ops-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    if (input.includes("/session"))
      return new Response(
        JSON.stringify({ ...session, is_staff: staff, is_superuser: superuser }),
        { headers: { "Content-Type": "application/json" } },
      );
    if (init?.method === "POST")
      return new Response(
        JSON.stringify({
          ok: true,
          messages: [{ level: "success", text: "Saved feed." }],
          redirect: "/ops/feeds/",
        }),
        { headers: { "Content-Type": "application/json" } },
      );
    return new Response(
      JSON.stringify(
        status === 200 ? content : { code: "feature_not_available", detail: "Ops unavailable." },
      ),
      { status, headers: { "Content-Type": "application/json" } },
    );
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
  return { client, router, fetchMock };
}

it("renders native React Ops tables, complete navigation, escaped cells and IST values without style injection", async () => {
  await show();
  expect(await screen.findByRole("heading", { name: "News feeds", level: 1 })).not.toHaveAttribute(
    "tabindex",
  );
  expect(screen.getByRole("cell", { name: "<b>Saved feed</b>" })).toBeInTheDocument();
  expect(document.querySelector(".data-table b")).toBeNull();
  const nav = within(screen.getByRole("navigation", { name: "Operations" }));
  expect(nav.getAllByRole("link")).toHaveLength(15);
  expect(nav.getByRole("link", { name: "Feeds" })).toHaveAttribute("aria-current", "page");
  expect(nav.getByRole("link", { name: "Feeds" }).querySelector("svg")).not.toBeNull();
  expect(document.querySelector(".ops-shell")).not.toBeNull();
  expect(screen.getByRole("cell", { name: "On" }).querySelector(".ops-status")).toHaveClass(
    "ops-tone-positive",
  );
  expect(screen.queryByRole("link", { name: "Open original Django page" })).not.toBeInTheDocument();
  expect(document.querySelector("style")).toBeNull();
});

it("searches, filters, sorts and paginates on the server with URL restoration", async () => {
  const { router, fetchMock } = await show();
  await screen.findByRole("heading", { name: "News feeds", level: 1 });
  fireEvent.change(screen.getByLabelText("Search News feeds"), { target: { value: "Saved" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => expect(router.state.location.search.q).toBe("Saved"));
  fireEvent.change(screen.getByLabelText("state"), { target: { value: "On" } });
  await waitFor(() => expect(router.state.location.search.state).toBe("On"));
  fireEvent.click(within(screen.getByRole("columnheader", { name: "Name" })).getByRole("button"));
  await waitFor(() => expect(router.state.location.search.sort).toBe("name"));
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => expect(router.state.location.search.page).toBe(2));
  expect(
    fetchMock.mock.calls.some(([url]) => url.includes("page=2") && url.includes("q=Saved")),
  ).toBe(true);
});

it("does not fetch operations for nonstaff and hides backups from staff navigation", async () => {
  const { fetchMock } = await show({ staff: false });
  await waitFor(() =>
    expect(screen.getByText("This Ops page requires additional permissions.")).toBeInTheDocument(),
  );
  expect(fetchMock.mock.calls.every(([url]) => url.includes("/session"))).toBe(true);
});

it("keeps read-only staff access while excluding backups", async () => {
  const readonly = zOpsPage.parse({
    ...page,
    sections: page.sections.map((section) => ({ ...section, forms: [] })),
  });
  await show({ superuser: false, body: readonly });
  await screen.findByRole("heading", { name: "News feeds", level: 1 });
  expect(screen.queryByRole("button", { name: "Add feed" })).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("navigation", { name: "Operations" })).queryByRole("link", {
      name: "Backups",
    }),
  ).not.toBeInTheDocument();
});

it("hides stale tables after permission revocation", async () => {
  const { fetchMock } = await show();
  await screen.findByRole("table", { name: "Feeds" });
  fetchMock.mockImplementation(
    async (input: string) =>
      new Response(
        JSON.stringify(
          input.includes("/session")
            ? { ...session, is_staff: true }
            : { code: "feature_not_available", detail: "Ops unavailable." },
        ),
        {
          status: input.includes("/session") ? 200 : 403,
          headers: { "Content-Type": "application/json" },
        },
      ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(await screen.findByText("Ops unavailable.")).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Feeds" })).not.toBeInTheDocument();
});

it("maps overview and nested edit paths to their real page endpoints", async () => {
  const { router, fetchMock } = await show({ path: "/ops/" });
  await screen.findByRole("heading", { level: 1, name: "News feeds" });
  expect(fetchMock.mock.calls.some(([url]) => url.includes("/pages/overview/"))).toBe(true);
  await act(async () => {
    await router.navigate({
      to: "/ops/$/",
      params: { _splat: "schedule/4" },
      search: opsSearchSchema.parse({}),
    });
  });
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/pages/schedule/4/"))).toBe(true),
  );
});

it("navigates Ops links within the mounted shell and keeps filter changes out of the page animation", async () => {
  const { router, fetchMock } = await show();
  await screen.findByRole("heading", { name: "News feeds", level: 1 });
  const shell = document.querySelector(".app-shell");
  const transition = document.querySelector(".page-transition");
  fireEvent.click(
    within(screen.getByRole("navigation", { name: "Operations" })).getByRole("link", {
      name: "Jobs",
    }),
  );
  await waitFor(() => expect(router.state.location.pathname).toBe("/ops/jobs/"));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/pages/jobs/"))).toBe(true),
  );
  expect(document.querySelector(".app-shell")).toBe(shell);
  expect(document.querySelector(".page-transition")).not.toBe(transition);
  const jobsTransition = document.querySelector(".page-transition");
  fireEvent.change(screen.getByLabelText("Search News feeds"), { target: { value: "query" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => expect(router.state.location.search.q).toBe("query"));
  expect(document.querySelector(".page-transition")).toBe(jobsTransition);
  expect(document.querySelector("style")).toBeNull();
});

it("preserves action notifications across React navigation", async () => {
  const { router, fetchMock } = await show();
  await screen.findByRole("button", { name: "Add feed" });
  fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
    const body = input.includes("/session")
      ? { ...session, is_staff: true, is_superuser: true }
      : init?.method === "POST"
        ? {
            ok: true,
            messages: [{ level: "success", text: "Schedule saved by React." }],
            redirect: "/ops/schedule/",
          }
        : page;
    return new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
    });
  });
  fireEvent.submit(screen.getByRole("button", { name: "Add feed" }).closest("form")!);
  await waitFor(() => expect(router.state.location.pathname).toBe("/ops/schedule/"));
  const notifications = await screen.findAllByText("Schedule saved by React.");
  expect(notifications).toHaveLength(2);
  expect(notifications.some((message) => message.closest(".app-toast"))).toBe(true);
  expect(screen.getByText("success").closest(".ops-status")).toHaveClass("ops-tone-positive");
});

it("renders semantic statistic cards and table states with distinct icons and a chart legend", async () => {
  await show({
    body: zOpsPage.parse({
      ...page,
      sections: [
        {
          title: "Job activity (last 7 days)",
          details: {
            Succeeded: { text: "12", value: 12, tone: "positive" },
            Failed: { text: "2", value: 2, tone: "negative" },
            "Success rate": { text: "86%", value: 86, tone: "negative" },
          },
          chart: [{ label: "19 Oct", value: 14, failed: 2 }],
          table: {
            columns: [{ key: "state", label: "Result" }],
            rows: [
              { cells: { state: { text: "Failed", tone: "negative" } } },
              { cells: { state: { text: "Waiting", tone: "warning" } } },
            ],
          },
        },
      ],
    }),
  });
  await screen.findByRole("heading", { name: "Job activity (last 7 days)" });
  expect(screen.getByText("12").closest(".ops-stat")).toHaveClass("ops-stat-positive");
  expect(screen.getByText("2").closest(".ops-stat")).toHaveClass("ops-stat-negative");
  expect(screen.getByRole("cell", { name: "Failed" }).querySelector(".ops-status")).toHaveClass(
    "ops-tone-negative",
  );
  expect(screen.getByRole("cell", { name: "Waiting" }).querySelector("svg")).not.toBeNull();
  expect(screen.getByText("Failed / alerts")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /daily totals and failures/ })).toBeInTheDocument();
});

function renderForm(value = form) {
  document.cookie = "csrftoken=ops-csrf; path=/";
  const onResult = vi.fn(async () => {});
  render(
    <ThemeProvider>
      <OpsActionForm form={value} onResult={onResult} />
    </ThemeProvider>,
  );
  return onResult;
}

it("posts FormData with CSRF without putting secret fields into query or mutation caches", async () => {
  const secret = zOpsForm.parse({
    ...form,
    fields: [{ name: "secret", label: "New secret", kind: "password" }],
  });
  let submitted = "";
  const fetch = vi.fn(async (_: string, init: RequestInit) => {
    submitted = String((init.body as FormData).get("secret"));
    expect(new Headers(init.headers).get("X-CSRFToken")).toBe("ops-csrf");
    return new Response(JSON.stringify({ ok: true, messages: [] }), {
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetch);
  const onResult = renderForm(secret);
  fireEvent.change(screen.getByLabelText("New secret"), { target: { value: "one-time-input" } });
  fireEvent.submit(screen.getByRole("button", { name: "Add feed" }).closest("form")!);
  await waitFor(() => expect(onResult).toHaveBeenCalledOnce());
  expect(submitted).toBe("one-time-input");
  expect(screen.getByLabelText("New secret")).toHaveValue("");
  expect(fetch).toHaveBeenCalledOnce();
});

it("preserves repeated feature values and prefixed instrument names", async () => {
  let submitted: [string, FormDataEntryValue][] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_: string, init: RequestInit) => {
      submitted = Array.from((init.body as FormData).entries());
      return new Response(JSON.stringify({ ok: true, messages: [] }), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const onResult = renderForm(
    zOpsForm.parse({
      ...form,
      fields: [
        { name: "allow", label: "News", kind: "checkbox", value: "news", checked: true },
        { name: "allow", label: "Markets", kind: "checkbox", value: "markets", checked: true },
        { name: "i4-weight", label: "Weight", kind: "number", value: "-0.25" },
      ],
    }),
  );
  fireEvent.submit(screen.getByRole("button", { name: "Add feed" }).closest("form")!);
  await waitFor(() => expect(onResult).toHaveBeenCalled());
  expect(submitted).toEqual([
    ["allow", "news"],
    ["allow", "markets"],
    ["i4-weight", "-0.25"],
  ]);
});

it("preserves destructive confirmations and sends nothing after cancellation", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  vi.spyOn(window, "confirm").mockReturnValue(false);
  renderForm(zOpsForm.parse({ ...form, confirmation: "Delete this feed?" }));
  fireEvent.submit(screen.getByRole("button", { name: "Add feed" }).closest("form")!);
  expect(window.confirm).toHaveBeenCalledWith("Delete this feed?");
  expect(fetch).not.toHaveBeenCalled();
});

it("requires CSRF and reports failures instead of pretending an action succeeded", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const onResult = renderForm();
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  fireEvent.submit(screen.getByRole("button", { name: "Add feed" }).closest("form")!);
  expect(
    await screen.findByText("Your security token is missing. Reload the page and try again."),
  ).toBeInTheDocument();
  expect(onResult).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
});

it("renders field validation, required restore upload, and cleared password values", () => {
  renderForm(
    zOpsForm.parse({
      ...form,
      errors: ["Nothing was saved."],
      fields: [
        { name: "backup", label: "Database snapshot", kind: "file", required: true },
        {
          name: "confirmation",
          label: "Type RESTORE",
          required: true,
          errors: ["Type RESTORE to continue."],
        },
      ],
    }),
  );
  expect(screen.getByLabelText("Database snapshot")).toHaveAttribute("type", "file");
  expect(screen.getByLabelText("Database snapshot")).toBeRequired();
  expect(screen.getByLabelText("Type RESTORE")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText("Nothing was saved.")).toHaveClass("ops-form-error");
  expect(screen.getByText("Type RESTORE to continue.").querySelector("svg")).not.toBeNull();
  expect(screen.getAllByRole("alert")).toHaveLength(2);
});

it("handles failed snapshot downloads as explicit feedback instead of a success-shaped file", async () => {
  document.cookie = "csrftoken=ops-csrf; path=/";
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            ok: false,
            messages: [{ level: "error", text: "Export failed." }],
            redirect: "/ops/backups/",
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  const result = await submitOpsForm(zOpsForm.parse({ ...form, download: true }), new FormData());
  expect(result.ok).toBe(false);
  expect(result.messages[0]?.text).toBe("Export failed.");
});

it("downloads the actual snapshot attachment using a temporary, cleaned-up anchor", async () => {
  document.cookie = "csrftoken=ops-csrf; path=/";
  const createObjectURL = vi.fn((_object: Blob | MediaSource) => "blob:test-snapshot");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    },
  );
  let filename = "";
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    expect(this.isConnected).toBe(true);
    filename = this.download;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response('{"records":[]}', {
          headers: {
            "Content-Type": "application/json",
            "Content-Disposition": 'attachment; filename="snapshot.json"',
          },
        }),
    ),
  );
  const result = await submitOpsForm(zOpsForm.parse({ ...form, download: true }), new FormData());
  expect(result.ok).toBe(true);
  expect(filename).toBe("snapshot.json");
  expect(createObjectURL.mock.calls[0]?.[0]).toBeInstanceOf(Blob);
  expect(document.querySelector('a[download="snapshot.json"]')).toBeNull();
  await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-snapshot"), {
    timeout: 1500,
  });
});

it("bounds URL query parameters and rejects unsupported operations", async () => {
  expect(() => opsSearchSchema.parse({ limit: 1001 })).toThrow();
  expect(() => opsSearchSchema.parse({ page: 0 })).toThrow();
  expect(() => opsSearchSchema.parse({ q: "x".repeat(201) })).toThrow();
  await expect(
    submitOpsForm(zOpsForm.parse({ ...form, action: "https://example.test" }), new FormData()),
  ).rejects.toThrow("not supported");
});
