import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { NewsPage } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const news: NewsPage = {
  items: [
    {
      id: 1,
      title: "Banks grow",
      url: "https://example.test/news",
      source: "Mint",
      published_at: "2026-10-07T03:00:00Z",
      sentiment: "positive",
      score: "7.3/10",
      relevance: "8.2/10",
      reason: "<b>Strong earnings</b>",
      companies: ["Example Bank"],
    },
  ],
  page: 1,
  pages: 2,
  total: 2,
  sources: ["Mint", "Other"],
  sentiments: [
    { value: "positive", label: "Good news" },
    { value: "negative", label: "Bad news" },
    { value: "neutral", label: "Neutral" },
    { value: "unscored", label: "Not scored yet" },
  ],
};
const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showNews({ path = "/app/news/", data = news, status = 200, staff = false } = {}) {
  document.cookie = "csrftoken=news-test-csrf; path=/";
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
                features: ["reports", "news"],
                navigation: [...session.navigation, { label: "News", url: "/news/" }],
              }
            : status === 200
              ? data
              : { code: "feature_not_available", detail: "News unavailable." },
        ),
        { status: isSession ? 200 : status, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/app",
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

it("shows scored articles, plain-text explanations, source links and IST publication times", async () => {
  await showNews();
  expect(await screen.findByRole("heading", { level: 1, name: "News" })).toHaveFocus();
  expect(screen.getByRole("link", { name: /Banks grow/ })).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: /Banks grow/ })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  expect(screen.getByText("7.3/10")).toHaveAttribute("data-sentiment", "positive");
  expect(screen.getByText(/8:30 am IST/i)).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "8.2/10" })).toBeInTheDocument();
  expect(screen.getByText("8.2/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("8.2/10")).toHaveAttribute("title", "High relevance");
  expect(screen.getByText("<b>Strong earnings</b>")).toBeInTheDocument();
  expect(document.querySelector(".data-table b")).toBeNull();
  expect(screen.getByText("Example Bank")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "News", current: "page" })).toHaveAttribute(
    "href",
    "/app/news/",
  );
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/news/");
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it.each([
  ["6.3/10", "caution", "Lower relevance"],
  ["6.4/10", "positive", "High relevance"],
  [null, "neutral", "Not available"],
])("renders relevance %s with the shared metric colors", async (relevance, tone, title) => {
  await showNews({ data: { ...news, items: [{ ...news.items[0], relevance }] } });
  const metric = await screen.findByTitle(title);
  expect(metric).toHaveAttribute("data-metric", "relevance");
  expect(metric).toHaveAttribute("data-tone", tone);
  expect(metric).toHaveTextContent(relevance ?? "\u2013");
  expect(screen.getByText("7.3/10")).toHaveAttribute("data-sentiment", "positive");
});

it("restores bookmarked filters and preserves them in pagination links", async () => {
  await showNews({
    path: "/app/news/?q=bank&source=Mint&sentiment=positive&page=2",
    data: { ...news, page: 2 },
  });
  expect(await screen.findByRole("searchbox", { name: "Search" })).toHaveValue("bank");
  expect(screen.getByRole("combobox", { name: "Score" })).toHaveValue("positive");
  expect(screen.getByRole("combobox", { name: "Source" })).toHaveValue("Mint");
  expect(screen.getByRole("link", { name: "Previous" })).toHaveAttribute(
    "href",
    expect.stringContaining("q=bank"),
  );
  expect(screen.getByRole("link", { name: "Previous" })).toHaveAttribute(
    "href",
    expect.stringContaining("sentiment=positive"),
  );
  expect(screen.queryByRole("link", { name: "Next" })).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(
    "/api/app/news?q=bank&source=Mint&sentiment=positive&page=2",
    expect.anything(),
  );
});

it("debounces typing, resets pagination, and updates the URL", async () => {
  const router = await showNews({ path: "/app/news/?page=2" });
  const input = await screen.findByRole("searchbox", { name: "Search" });
  input.focus();
  fireEvent.change(input, { target: { value: "b" } });
  fireEvent.change(input, { target: { value: "bank" } });
  await waitFor(() => expect(router.state.location.search.q).toBe("bank"));
  expect(router.state.location.search.page).toBe(1);
  const requests = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
  expect(requests.some((url) => url.includes("q=b&"))).toBe(false);
  expect(input).toHaveFocus();
});

it("applies score and source changes immediately and restores them on back navigation", async () => {
  const router = await showNews();
  fireEvent.change(await screen.findByRole("combobox", { name: "Score" }), {
    target: { value: "negative" },
  });
  await waitFor(() => expect(router.state.location.search.sentiment).toBe("negative"));
  fireEvent.change(screen.getByRole("combobox", { name: "Source" }), { target: { value: "Mint" } });
  await waitFor(() => expect(router.state.location.search.source).toBe("Mint"));
  router.history.back();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Source" })).toHaveValue(""));
  expect(screen.getByRole("combobox", { name: "Score" })).toHaveValue("negative");
});

it("applies on submit, clears filters, and cancels pending search input", async () => {
  const router = await showNews({ path: "/app/news/?source=Mint&sentiment=positive&page=2" });
  fireEvent.change(await screen.findByRole("searchbox"), { target: { value: "banks" } });
  fireEvent.submit(screen.getByRole("searchbox").closest("form")!);
  await waitFor(() => expect(router.state.location.search.q).toBe("banks"));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "pending" } });
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await waitFor(() =>
    expect(router.state.location.search).toEqual({ q: "", sentiment: "", source: "", page: 1 }),
  );
  await new Promise((resolve) => setTimeout(resolve, 350));
  expect(router.state.location.search.q).toBe("");
  expect(screen.getByRole("searchbox")).toHaveValue("");
});

it.each([false, true])("keeps empty-state operational hints staff-only: %s", async (staff) => {
  await showNews({ staff, data: { ...news, items: [], total: 0, pages: 1 } });
  expect(await screen.findByText(/No article matches/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "feeds" }) !== null).toBe(staff);
  expect(screen.queryByRole("navigation", { name: "News pages" })).not.toBeInTheDocument();
});

it("does not show operational hints for empty filtered results", async () => {
  await showNews({
    staff: true,
    path: "/app/news/?q=nothing",
    data: { ...news, items: [], total: 0, pages: 1 },
  });
  expect(await screen.findByText(/No article matches/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "feeds" })).not.toBeInTheDocument();
});

it("handles missing scores and dates without inventing values or unsafe links", async () => {
  await showNews({
    data: {
      ...news,
      items: [
        {
          ...news.items[0]!,
          score: null,
          relevance: null,
          published_at: null,
          sentiment: "unscored",
          url: "javascript:alert(1)",
          companies: [],
          reason: "",
        },
      ],
    },
  });
  await waitFor(() =>
    expect(screen.getByText(/Not scored yet/, { selector: "p" })).toBeInTheDocument(),
  );
  expect(screen.queryByRole("link", { name: /Banks grow/ })).not.toBeInTheDocument();
  expect(screen.getByText("Source link unavailable.")).toBeInTheDocument();
  expect(screen.queryByText("7.3/10")).not.toBeInTheDocument();
});

it("provides a News-specific recovery link for permission errors", async () => {
  await showNews({ status: 403 });
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Not on your account" })).toBeInTheDocument(),
  );
  expect(screen.getByRole("link", { name: "Back to News" })).toHaveAttribute("href", "/app/news/");
  expect(screen.queryByRole("link", { name: "Back to Reports" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("rejects contract drift visibly", async () => {
  await showNews({ data: { ...news, items: [{ ...news.items[0]!, published_at: "not-a-date" }] } });
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Unable to load this page" })).toBeInTheDocument(),
  );
  expect(screen.getByText(/The news response does not match/)).toBeInTheDocument();
});

it("uses server sorting and page size without losing news filters", async () => {
  const router = await showNews({
    path: "/app/news/?q=bank&source=Mint&sentiment=positive&page=2",
  });
  fireEvent.click(await screen.findByRole("button", { name: "Sentiment" }));
  await waitFor(() =>
    expect(router.state.location.search).toMatchObject({
      sort: "score",
      q: "bank",
      source: "Mint",
      sentiment: "positive",
      page: 1,
    }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Rows per page for News" }), {
    target: { value: "50" },
  });
  await waitFor(() => expect(router.state.location.search.page_size).toBe(50));
  expect(fetch).toHaveBeenCalledWith(
    "/api/app/news?q=bank&source=Mint&sentiment=positive&page=1&sort=score&page_size=50",
    expect.anything(),
  );
});
