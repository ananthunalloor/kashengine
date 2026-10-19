import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { IpoDetail, IpoPage } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const ipo: IpoDetail = {
  id: 1,
  name: "Example Ltd",
  category: "Mainboard",
  status: "open",
  dates: "7 Oct to 9 Oct",
  price_band: "Rs 100",
  gmp: "+20.0%",
  subscribed: "0.0x",
  listing_gain: "-",
  verdict: "good",
  score: "8.2/10",
  facts: [
    { label: "GMP", value: "Rs 20 (+20.0%) (updated 3 days ago)" },
    { label: "Price band", value: "Rs 90 to Rs 100" },
  ],
  signals: [
    { name: "GMP", value: "+20.0%", signal: "7.8/10" },
    { name: "Subscription", value: "0.0x", signal: "1.0/10" },
  ],
  notes: ["<b>Stale metric</b>"],
  scored_at: "2026-10-07T03:00:00Z",
  source_url: "https://example.test/ipo",
};
const list: IpoPage = {
  items: [ipo],
  page: 1,
  pages: 2,
  total: 2,
  statuses: [
    { value: "", label: "Active" },
    { value: "all", label: "All" },
    { value: "listed", label: "Listed" },
    { value: "open", label: "Open" },
  ],
  verdicts: [
    { value: "good", label: "Likely good" },
    { value: "unknown", label: "No verdict" },
  ],
  categories: [
    { value: "mainboard", label: "Mainboard" },
    { value: "sme", label: "SME" },
  ],
};
const clients: QueryClient[] = [];

it("sorts IPO metrics on the server and retains board/status filters across size changes", async () => {
  const router = await showIpos({ path: "/ipos/?category=sme&status=listed&page=2" });
  fireEvent.click(await screen.findByRole("button", { name: "GMP" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      category: "sme",
      status: "listed",
      page: 1,
      sort: "gmp",
    }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for IPOs" }), {
    target: { value: "50" },
  });
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      category: "sme",
      status: "listed",
      page: 1,
      sort: "gmp",
      page_size: 50,
    }),
  );
});

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showIpos({
  path = "/ipos/",
  page = list,
  detail = ipo,
  status = 200,
  staff = false,
} = {}) {
  document.cookie = "csrftoken=ipos-test-csrf; path=/";
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
                features: [...session.features, "ipos"],
                navigation: [...session.navigation, { label: "IPOs", url: "/ipos/" }],
              }
            : status !== 200
              ? {
                  code: status === 404 ? "not_found" : "feature_not_available",
                  detail: "IPO unavailable.",
                }
              : input.startsWith("/api/app/ipos?")
                ? page
                : detail,
        ),
        {
          status: isSession ? 200 : status,
          headers: { "Content-Type": "application/json" },
        },
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

it("shows issue cards, metrics and preview-only navigation", async () => {
  await showIpos();
  expect(await screen.findByRole("heading", { level: 1, name: "IPOs" })).not.toHaveAttribute(
    "tabindex",
  );
  expect(screen.getByRole("link", { name: "Example Ltd" })).toHaveAttribute("href", "/ipos/1/");
  expect(screen.getByText("0.0x")).toBeInTheDocument();
  expect(screen.getByText("+20.0%")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("8.2/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("0.0x")).not.toHaveAttribute("data-tone");
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/ipos/");
  expect(screen.getByRole("link", { name: "IPOs", current: "page" })).toHaveAttribute(
    "href",
    "/ipos/",
  );
  expect(screen.getByRole("combobox", { name: "Status" })).toHaveValue("");
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("navigates to saved facts and evidence without leaving React", async () => {
  const router = await showIpos();
  fireEvent.click(await screen.findByRole("link", { name: "Example Ltd" }));
  expect(await screen.findByRole("heading", { name: "The issue" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/ipos/1/");
  expect(screen.getByRole("heading", { level: 1 })).not.toHaveAttribute("tabindex");
  expect(screen.getByText(/Good, score/)).toHaveTextContent("Good, score 8.2/10");
  expect(screen.getByText(/updated 3 days ago/)).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("7.8/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("1.0/10")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByRole("table", { name: "Saved scoring inputs" })).toHaveTextContent("7.8/10");
  expect(screen.getByText("<b>Stale metric</b>")).toBeInTheDocument();
  expect(document.querySelector(".ipo-detail-grid b")).toBeNull();
  expect(screen.getByText(/8:30 am IST/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Source page/ })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("colors negative listing gains, GMP and saved news scores without coloring prices", async () => {
  await showIpos({
    path: "/ipos/1/",
    detail: {
      ...ipo,
      score: "4.2/10",
      facts: [
        { label: "GMP", value: "\u20b9-12 (-12.0%) (updated 2 hours ago)" },
        { label: "Listing gain", value: "-3.2%" },
        { label: "Price band", value: "\u20b9100" },
      ],
      signals: [{ name: "News", value: "4.8/10", signal: "4.8/10" }],
    },
  });
  expect(await screen.findByText(/updated 2 hours ago/)).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("-3.2%")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("4.2/10")).toHaveAttribute("data-tone", "negative");
  expect(screen.getAllByText("4.8/10").every((node) => node.dataset.tone === "negative")).toBe(
    true,
  );
  expect(screen.getByText("\u20b9100")).not.toHaveAttribute("data-tone");
});

it("restores all bookmarked filters and retains them in pagination", async () => {
  await showIpos({
    path: "/ipos/?q=Example&status=listed&verdict=good&category=sme&page=2",
    page: { ...list, page: 2 },
  });
  expect(await screen.findByRole("searchbox")).toHaveValue("Example");
  expect(screen.getByRole("combobox", { name: "Status" })).toHaveValue("listed");
  expect(screen.getByRole("combobox", { name: "Verdict" })).toHaveValue("good");
  expect(screen.getByRole("combobox", { name: "Board" })).toHaveValue("sme");
  const href = screen.getByRole("link", { name: "Previous" }).getAttribute("href")!;
  expect(href).toContain("status=listed");
  expect(href).toContain("category=sme");
  expect(href).toContain("verdict=good");
  expect(screen.queryByRole("link", { name: "Next" })).not.toBeInTheDocument();
});

it("debounces search, resets page, and applies board/verdict/status filters", async () => {
  const router = await showIpos({ path: "/ipos/?page=2" });
  const input = await screen.findByRole("searchbox");
  input.focus();
  fireEvent.change(input, { target: { value: "Ex" } });
  fireEvent.change(input, { target: { value: "Example" } });
  await waitFor(() => expect(router.state.location.search.q).toBe("Example"));
  expect(router.state.location.search.page).toBe(1);
  expect(input).toHaveFocus();
  for (const [label, value, field] of [
    ["Board", "sme", "category"],
    ["Verdict", "good", "verdict"],
    ["Status", "listed", "status"],
  ] as const) {
    fireEvent.change(screen.getByRole("combobox", { name: label }), { target: { value } });
    await waitFor(() => expect(router.state.location.search[field]).toBe(value));
  }
  router.history.back();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Status" })).toHaveValue(""));
});

it("clears pending typing and resets to Active", async () => {
  const router = await showIpos({ path: "/ipos/?status=all&verdict=good&category=sme" });
  fireEvent.change(await screen.findByRole("searchbox"), { target: { value: "pending" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await waitFor(() =>
    expect(router.state.location.search).toEqual({
      q: "",
      status: "",
      verdict: "",
      category: "",
      page: 1,
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 350));
  expect(screen.getByRole("searchbox")).toHaveValue("");
  expect(router.state.location.search.q).toBe("");
});

it.each([false, true])("keeps empty-list hints staff-only: %s", async (staff) => {
  await showIpos({ staff, page: { ...list, items: [], pages: 1, total: 0 } });
  expect(await screen.findByText(/No IPO matches/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ops > Settings > IPOs" }) !== null).toBe(staff);
  expect(screen.queryByRole("navigation", { name: "IPO pages" })).not.toBeInTheDocument();
});

it("handles unscored issues and unsafe source links without inventing values", async () => {
  await showIpos({
    path: "/ipos/1/",
    detail: {
      ...ipo,
      verdict: "unknown",
      score: null,
      signals: [],
      notes: [],
      scored_at: null,
      source_url: "javascript:alert(1)",
    },
  });
  expect(await screen.findByText("There is no usable signal yet.")).toBeInTheDocument();
  expect(screen.getByText("Unknown")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Source page/ })).not.toBeInTheDocument();
  expect(screen.getByText("Source link unavailable.")).toBeInTheDocument();
});

it.each([403, 404])("shows IPO-specific recovery for %s", async (status) => {
  await showIpos({ path: "/ipos/1/", status });
  await waitFor(() =>
    expect(
      screen.getByRole("heading", {
        name: status === 404 ? "IPO not found" : "Not on your account",
      }),
    ).toBeInTheDocument(),
  );
  expect(screen.getByRole("link", { name: "Back to IPOs" })).toHaveAttribute("href", "/ipos/");
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
});

it("rejects detail contract drift visibly", async () => {
  await showIpos({ path: "/ipos/1/", detail: { ...ipo, scored_at: "invalid" } });
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Unable to load this page" })).toBeInTheDocument(),
  );
  expect(screen.getByText(/The IPO response does not match/)).toBeInTheDocument();
});
