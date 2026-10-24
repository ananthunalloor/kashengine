import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { CompanyDetail } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const detail: CompanyDetail = {
  company: {
    id: 1,
    name: "<b>Example</b>",
    symbol: "EXAMPLE",
    sector: "Energy",
    screener_url: "",
    last_updated: null,
  },
  summary: "A saved business summary.",
  instrument_key: "NSE_EQ|INE002A01018",
  fundamentals: { "key-ratios": [{ name: "P/E", company_value: "20", sector_value: "15" }] },
  fundamentals_source: "Upstox",
  fundamentals_as_of: "2026-10-22T10:00:00Z",
  errors: {},
  markets_available: true,
  news_available: true,
  ipos_available: true,
  quote: {
    price: 110,
    previous_close: 100,
    change_pct: 10,
    volume: 1000,
    mode: "snapshot",
    as_of: "2026-10-22T10:00:00Z",
    received_at: "2026-10-22T10:00:01Z",
  },
  candles: [
    { day: "2026-10-21", open: 99, high: 102, low: 98, close: 100, volume: 100 },
    { day: "2026-10-22", open: 100, high: 112, low: 99, close: 110, volume: 200 },
  ],
  outlook: {
    target_date: "2026-10-23",
    direction: "up",
    score: 0.5,
    momentum_score: 0.6,
    news_score: 0.3,
    created_at: "2026-10-22T11:00:00Z",
    inputs: { method: "momentum-news-v1", return_20_sessions_pct: 6 },
  },
  news: [
    {
      title: "Company story",
      url: "javascript:alert(1)",
      source: "Test",
      published_at: null,
      sentiment_score: 0.3,
      relevance: 0.8,
      sentiment_reason: "Saved reason",
    },
  ],
  ipos: [],
};
const clients: QueryClient[] = [];
afterEach(() => {
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function show(path: string, body: unknown) {
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: string) =>
        new Response(
          JSON.stringify(
            input === "/api/app/session"
              ? { ...session, features: [...session.features, "companies", "markets"] }
              : body,
          ),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
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
}

it("renders saved summary, fundamentals, chart, all scores and safe news text", async () => {
  await show("/companies/1/", detail);
  expect(
    await screen.findByRole("heading", { level: 1, name: "<b>Example</b>" }),
  ).toBeInTheDocument();
  expect(screen.getByText("A saved business summary.")).toBeInTheDocument();
  expect(document.querySelector("main h1 b")).toBeNull();
  expect(screen.getByRole("img", { name: /Saved closing prices/ })).toBeInTheDocument();
  expect(screen.getByText(/Combined score: 0.500/)).toBeInTheDocument();
  expect(screen.getByText(/Momentum score: 0.600/)).toBeInTheDocument();
  expect(screen.getByText(/News score: 0.300/)).toBeInTheDocument();
  expect(screen.getByText(/older observation, not live/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Company story" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "key ratios" }));
  expect(await screen.findByText("P/E")).toBeInTheDocument();
  expect(screen.getByText(/not been backtested/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/app/companies/1", expect.anything());
});

it("explains absent history and outlook without fabricating prices or scores", async () => {
  await show("/companies/1/", {
    ...detail,
    quote: null,
    candles: [],
    outlook: null,
    fundamentals: {},
    summary: "",
  });
  expect(await screen.findByText(/No provider business summary/)).toBeInTheDocument();
  expect(screen.getByText(/No saved quote/)).toBeInTheDocument();
  expect(screen.getByText(/No saved daily price history/)).toBeInTheDocument();
  expect(screen.getByText(/At least 21 recent/)).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("keeps unavailable market, news and IPO datasets out of the page", async () => {
  await show("/companies/1/", {
    ...detail,
    markets_available: false,
    news_available: false,
    ipos_available: false,
    quote: null,
    candles: [],
    outlook: null,
    news: [],
    ipos: [],
  });
  expect(await screen.findByText(/require Markets access/)).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Stock trend" })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Company news and sentiment scores" }),
  ).not.toBeInTheDocument();
});

it("shows saved-company market observations and internal company links", async () => {
  await show("/markets/live/", {
    items: [{ id: 1, name: "Example", symbol: "EXAMPLE", quote: detail.quote, error: "" }],
    page: 1,
    pages: 1,
    total: 1,
    page_size: 25,
    upstox_enabled: false,
  });
  expect(await screen.findByRole("heading", { name: "Company market data" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Example" })).toHaveAttribute("href", "/companies/1/");
  expect(screen.getByText("110")).toBeInTheDocument();
  expect(screen.getByText("Upstox ingestion is disabled")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/app/markets/companies?q=&page=1", expect.anything());
});
