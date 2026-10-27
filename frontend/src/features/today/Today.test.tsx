import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { Session, Today } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const data: Today = {
  today: "2026-10-19",
  markets: {
    outlook: {
      date: "2026-10-16",
      direction: "down",
      strength: "6.4/10",
      strength_label: "strong",
      news_score: "5.5/10",
      news_articles: 12,
      global_score: "2.8/10",
      cues: [{ name: "S&P 500", change: "\u22121.25%", as_of: "2026-10-15" }],
      notes: ["<b>Saved outlook note</b>"],
    },
    stats: {
      total: 2,
      correct: 1,
      accuracy: "50%",
      baseline_direction: "up",
      baseline_accuracy: "50%",
      high_confidence: { n: 1, correct: 1 },
      recent: { n: 2, correct: 1 },
      pending: 1,
      enough_results: false,
    },
    quotes: [{ name: "Nifty 50", day: "2026-10-16", close: "24500.00", change: "+0.40%" }],
  },
  news: {
    since: "2026-10-17T15:30:00Z",
    articles: 12,
    positive: 6,
    negative: 6,
    good: [
      {
        title: "<b>Strong sales</b>",
        source: "Mint",
        url: "https://example.test/story",
        score: "9.1/10",
        reason: "<b>Plain explanation</b>",
        companies: ["Example Ltd"],
      },
    ],
    bad: [
      {
        title: "Weak sales",
        source: "Reuters",
        url: "javascript:alert(1)",
        score: "1.9/10",
        reason: "",
        companies: [],
      },
    ],
  },
  ipos: {
    likely_good: [
      {
        name: "Example Ltd",
        category: "mainboard",
        status: "open",
        open_date: "2026-10-19",
        close_date: "2026-10-21",
        price_band: "\u20b9100",
        gmp: "+20.0%",
        subscribed: "2.0x",
        verdict: "good",
        score: "8.2/10",
      },
    ],
    open_now: [],
    upcoming: [],
    days_ahead: 7,
  },
  report: { date: "2026-10-16", prediction: "up", strength: "7.3/10" },
};
const fullSession: Session = {
  ...session,
  features: ["markets", "news", "ipos", "reports"],
  navigation: [
    { label: "Today", url: "/dashboard/" },
    { label: "Markets", url: "/markets/" },
    { label: "News", url: "/news/" },
    { label: "IPOs", url: "/ipos/" },
    { label: "Reports", url: "/reports/" },
  ],
};
const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showToday({
  body = data,
  status = 200,
  account = fullSession,
}: { body?: unknown; status?: number; account?: Session } = {}) {
  document.cookie = "csrftoken=today-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const isSession = input === "/api/app/session";
      const result = isSession
        ? account
        : input === "/api/app/today"
          ? body
          : {
              date: "2026-10-16",
              prediction: "up",
              strength: "7.3/10",
              text: "Saved report",
              deliveries: [],
              older: null,
              newer: null,
            };
      return new Response(JSON.stringify(result), {
        status: isSession ? 200 : status,
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
    history: createMemoryHistory({ initialEntries: ["/dashboard/"] }),
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

it("renders the dated overview, evidence, baseline and colored values without injected styles", async () => {
  await showToday();
  expect(await screen.findByRole("heading", { level: 1, name: "Today" })).not.toHaveAttribute(
    "tabindex",
  );
  expect(document.title).toBe("Today | Kash Engine");
  expect(screen.getByRole("link", { name: "Today", current: "page" })).toHaveAttribute(
    "href",
    "/dashboard/",
  );
  expect(screen.getByText("The Nifty 50 is likely to fall.")).toBeInTheDocument();
  expect(screen.getByText(/Outlook for/)).toHaveTextContent("Friday, 16 October 2026");
  expect(screen.getByText("Monday, 19 October 2026")).toBeInTheDocument();
  expect(screen.getByText("6.4/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("2.8/10")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("\u22121.25%")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("+0.40%")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText(/right on 1 of 2/)).toHaveTextContent("too few results");
  expect(screen.getByText("<b>Saved outlook note</b>")).toBeInTheDocument();
  expect(screen.getByText("<b>Plain explanation</b>")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Strong sales/ })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  expect(screen.queryByRole("link", { name: "Weak sales" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("table")).toHaveLength(4);
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("b")).toBeNull();
  expect(document.querySelector("style")).toBeNull();
  expect(fetch).toHaveBeenCalledWith("/api/app/today", expect.anything());
});

it("filters and searches the bounded story table without removing context", async () => {
  await showToday();
  const news = within(await screen.findByRole("region", { name: "Stories that move the market" }));
  fireEvent.change(news.getByRole("combobox", { name: "Sentiment" }), {
    target: { value: "Bad for stocks" },
  });

  expect(news.getByRole("cell", { name: /^Weak sales/ })).toBeInTheDocument();
  expect(news.queryByText("<b>Strong sales</b>")).not.toBeInTheDocument();
  fireEvent.change(news.getByRole("searchbox"), { target: { value: "no match" } });
  expect(news.getByText(/No results match/)).toBeInTheDocument();
  fireEvent.change(news.getByRole("searchbox"), { target: { value: "" } });
  fireEvent.change(news.getByRole("combobox", { name: "Sentiment" }), { target: { value: "" } });
  fireEvent.click(news.getByRole("button", { name: "Score" }));
  expect(news.getByRole("columnheader", { name: "Score" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
});

it("shows the news-driven stock watchlist when supplied by the feature-filtered API", async () => {
  await showToday({
    body: {
      ...data,
      stocks_watch: {
        as_of: "2026-10-19T04:30:00Z",
        since: "2026-10-17T16:30:00Z",
        session_date: "2026-10-19",
        next_session: "2026-10-19",
        session_state: "open",
        sampled_articles: 0,
        truncated: false,
        items: [],
      },
    },
    account: { ...fullSession, features: [...fullSession.features, "companies"] },
  });
  expect(await screen.findByRole("heading", { name: "Stocks to watch today" })).toBeInTheDocument();
  expect(screen.getByText("No news-backed stocks to watch yet")).toBeInTheDocument();
});

it("keeps the latest report link inside React", async () => {
  const router = await showToday();
  fireEvent.click(await screen.findByRole("link", { name: "Read it" }));
  expect(await screen.findByRole("article", { name: "Report text" })).toHaveTextContent(
    "Saved report",
  );
  await waitFor(() => expect(router.state.location.pathname).toBe("/reports/2026-10-16/"));
});

it("omits every unavailable section and its links", async () => {
  await showToday({
    body: { today: data.today, markets: null, news: null, ipos: null, report: null },
    account: {
      ...session,
      features: [],
      navigation: [
        { label: "Today", url: "/dashboard/" },
        { label: "Account", url: "/account/" },
      ],
    },
  });
  expect(await screen.findByRole("heading", { name: "Welcome" })).toBeInTheDocument();
  expect(screen.getByText(/No feature is on/)).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "No outlook yet" })).not.toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Stocks to watch today" })).not.toBeInTheDocument();
  for (const name of ["See the history", "All news", "All IPOs", "Read it"])
    expect(screen.queryByRole("link", { name })).not.toBeInTheDocument();
});

it("guides accounts that only have sections outside the daily overview", async () => {
  await showToday({
    body: { today: data.today, markets: null, news: null, ipos: null, report: null },
    account: { ...session, features: ["companies", "delivery"] },
  });
  expect(await screen.findByRole("region", { name: "Your overview" })).toHaveTextContent(
    "Open your available sections from the navigation.",
  );
  expect(screen.queryByText(/No feature is on/)).not.toBeInTheDocument();
});

it.each([false, true])(
  "handles empty states with staff guidance only for staff=%s",
  async (staff) => {
    await showToday({
      body: {
        ...data,
        markets: {
          ...data.markets,
          outlook: null,
          quotes: [],
          stats: { ...data.markets!.stats, total: 0 },
        },
        news: { ...data.news, good: [], bad: [] },
        ipos: { ...data.ipos, likely_good: [], open_now: [], upcoming: [] },
        report: null,
      },
      account: { ...fullSession, is_staff: staff },
    });
    expect(await screen.findByRole("heading", { name: "No outlook yet" })).toBeInTheDocument();
    expect(screen.getByText(/There are no results yet to check/)).toBeInTheDocument();
    expect(screen.getByText(/No strong stories yet/)).toBeInTheDocument();
    expect(screen.getByText("No IPO is open or coming soon.")).toBeInTheDocument();
    expect(screen.getByText("No saved closes yet.")).toBeInTheDocument();
    expect(!!screen.queryByRole("link", { name: "Jobs" })).toBe(staff);
    expect(screen.queryByRole("link", { name: "Read it" })).not.toBeInTheDocument();
  },
);

it.each([403, 429, 500])("shows a visible Today recovery state for %s", async (status) => {
  await showToday({
    status,
    body: {
      code: status === 403 ? "subscription_required" : "unavailable",
      detail: "Today unavailable.",
    },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("Today unavailable.");
  expect(screen.getByRole("link", { name: "Back to Today" })).toHaveAttribute(
    "href",
    "/dashboard/",
  );
  expect(!!screen.queryByRole("button", { name: "Try again" })).toBe(status !== 403);
});

it("rejects contract drift instead of showing a success-shaped empty dashboard", async () => {
  await showToday({ body: { today: "2026-10-19" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("The Today response does not match");
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
