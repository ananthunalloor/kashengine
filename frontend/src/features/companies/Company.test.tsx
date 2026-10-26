import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import { metricAssessment, projectClosingPrices } from "./Company";
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
  fundamentals: {
    "key-ratios": [
      { name: "P/E", company_value: "20", sector_value: "15" },
      { name: "ROE", company_value: "20", sector_value: "15" },
      { name: "Debt to equity", company_value: "2", sector_value: "1" },
    ],
  },
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
    {
      title: "Market pressure story",
      url: "https://news.example.test/market-pressure",
      source: "Wire",
      published_at: "2026-10-22T09:00:00Z",
      sentiment_score: -0.4,
      relevance: 0.7,
      sentiment_reason: "Saved negative reason",
    },
  ],
  ipos: [],
};
const clients: QueryClient[] = [];
afterEach(() => {
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

it("extends a straight-line history at the fitted daily slope", () => {
  const candles = Array.from({ length: 20 }, (_, index) => ({
    day: `2026-10-${String(index + 1).padStart(2, "0")}`,
    open: 100 + index,
    high: 101 + index,
    low: 99 + index,
    close: 100 + index,
    volume: 100,
  }));

  const projection = projectClosingPrices(candles);

  expect(projection).toHaveLength(21);
  expect(projection[0]).toEqual({ label: "2026-10-20", value: 119 });
  expect(projection.at(-1)).toEqual({ label: "T+20", value: 139 });
  expect(projectClosingPrices(candles.slice(1))).toEqual([]);
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

it("renders saved company data and a history-only trend projection", async () => {
  const candles = Array.from({ length: 20 }, (_, index) => {
    const close = 100 + index;
    return {
      day: `2026-10-${String(index + 1).padStart(2, "0")}`,
      open: close,
      high: close + 1,
      low: close - 1,
      close,
      volume: 100,
    };
  });
  await show("/companies/1/", { ...detail, candles });
  expect(
    await screen.findByRole("heading", { level: 1, name: "<b>Example</b>" }),
  ).toBeInTheDocument();
  expect(screen.getByText("A saved business summary.")).toBeInTheDocument();
  expect(document.querySelector("main h1 b")).toBeNull();
  expect(screen.getByLabelText(/20-session history-only linear projection/)).toBeInTheDocument();
  expect(screen.getByText(/Daily OHLC candles with a history-only projection/)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Daily candlestick chart/ })).toBeInTheDocument();
  expect(screen.getByText(/older observation, not live/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Company story" })).not.toBeInTheDocument();
  expect(
    within(screen.getByRole("table", { name: "Fundamental metrics" })).getByText("P/E"),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Is this company overvalued?" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Valuation" })).toHaveAttribute(
    "href",
    "#company-valuation",
  );
  expect(screen.getAllByText("20")).toHaveLength(2);
  expect(screen.getAllByText("15")).toHaveLength(2);
  const fundamentals = within(screen.getByRole("table", { name: "Fundamental metrics" }));
  expect(fundamentals.getByText("Higher multiple · context needed")).toBeInTheDocument();
  expect(fundamentals.getByText("Favorable · stronger vs sector")).toBeInTheDocument();
  expect(fundamentals.getByText("Unfavorable · higher leverage")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Assessment" }), {
    target: { value: "Favorable · stronger vs sector" },
  });
  expect(fundamentals.getByText("ROE")).toBeInTheDocument();
  expect(fundamentals.queryByText("Debt to equity")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Assessment" }), {
    target: { value: "" },
  });
  expect(screen.queryByText(/Upstox/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Provider:/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "About P/E" })).toBeInTheDocument();
  expect(
    screen.getByRole("region", {
      name: "Company news table, scroll horizontally for more columns",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("Positive · 0.3")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Sentiment" }), {
    target: { value: "Negative" },
  });
  expect(screen.getByRole("link", { name: /Market pressure story/ })).toBeInTheDocument();
  expect(screen.queryByText("Company story")).not.toBeInTheDocument();
  expect(screen.getByText(/not been backtested/)).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Prediction accuracy & deviations" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Engine Outlook")).toBeInTheDocument();
  expect(screen.getByText("Bullish")).toBeInTheDocument();
  expect(screen.getByText("Signal Score: 0.500")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Company sections" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Trade setup watchlist" })).toBeInTheDocument();
  expect(screen.getByText("Wait / insufficient data")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith("/api/app/companies/1", expect.anything());
});

it("explains absent history without fabricating prices or a projection", async () => {
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
  expect(screen.getByText(/At least 20 saved daily closes/)).toBeInTheDocument();
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
  expect(screen.queryByRole("heading", { name: "Trade setup watchlist" })).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Prediction accuracy & deviations" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Company news and sentiment scores" }),
  ).not.toBeInTheDocument();
});

it("assesses only valid sector comparisons and does not treat blank values as zero", () => {
  for (const missing of ["", " ", "-", "N/A", null, undefined, Number.NaN, true]) {
    expect(metricAssessment("ROE", missing, "15").label).toBe("Not assessable");
    expect(metricAssessment("ROE", "20", missing).label).toBe("No sector benchmark");
  }
  expect(metricAssessment("ROE", "0", "15").label).toBe("Unfavorable · weaker vs sector");
  expect(metricAssessment("ROE", "20.5%", "15%").label).toBe("Favorable · stronger vs sector");
  expect(metricAssessment("Debt to equity", "1", "2").label).toBe("Favorable · lower leverage");
  expect(metricAssessment("Debt to equity", "-1", "2").label).toContain("Not comparable");
  expect(metricAssessment("P/E", "-5", "15").label).toContain("Not comparable");
  expect(metricAssessment("P/E", "0", "15").label).toContain("Not comparable");
  expect(metricAssessment("P/E", "-5", "-5").label).toContain("Not comparable");
  expect(metricAssessment("ROE", "15", 15).label).toBe("In line with sector");
  expect(metricAssessment("Revenue", "1,200", "900").label).toBe("Above sector · context needed");
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
