import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { liveQuoteSchema, type LiveMarket } from "../api/liveQuotes";
import { LiveCompanyQuote, LiveIndices, marketStatusLabel } from "./LiveMarket";

const now = new Date().toISOString();
const nifty = liveQuoteSchema.parse({
  key: "NSE_INDEX|Nifty 50",
  kind: "index",
  name: "Nifty 50",
  ltp: 24500.5,
  as_of: now,
  previous_close: 24600,
  change: -99.5,
  change_pct: -0.4,
  high: 24650,
  low: 24480,
});
const equity = liveQuoteSchema.parse({
  key: "NSE_EQ|INE000000001",
  kind: "equity",
  name: "Example",
  symbol: "EXAMPLE",
  company_id: 7,
  ltp: 101.25,
  as_of: "2020-01-01T04:30:00Z",
  previous_close: 100,
  change: 1.25,
  change_pct: 1.25,
  open: 100.5,
  high: 102,
  low: 99.5,
  volume: 12345,
  average_price: 101,
  total_buy_qty: 300,
  total_sell_qty: 100,
  depth: [{ bid_price: 101.2, bid_qty: 10, ask_price: 101.3, ask_qty: 5 }],
});
const status = { segments: { NSE_EQ: "NORMAL_OPEN" }, as_of: now };

function renderUi(ui: React.ReactNode) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

it("labels exchange states", () => {
  expect(marketStatusLabel(status)).toBe("Market open");
  expect(marketStatusLabel({ segments: { NSE_EQ: "CLOSING_END" }, as_of: now })).toBe(
    "Market closed",
  );
  expect(marketStatusLabel(null)).toBeNull();
});

it("shows live index tiles with change and range", () => {
  const live: LiveMarket = {
    connection: "live",
    indices: [nifty],
    companies: new Map(),
    status,
  };
  renderUi(<LiveIndices live={live} />);
  const tile = screen.getByRole("article", { name: "Nifty 50 live" });
  expect(within(tile).getByText("24,500.50")).toBeInTheDocument();
  expect(within(tile).getByText(/-99\.50/)).toBeInTheDocument();
  expect(within(tile).getByText(/Day range 24,480\.00/)).toBeInTheDocument();
  expect(tile).toHaveTextContent(/Last trade \d/);
  expect(screen.getByText("Market open")).toBeInTheDocument();
  expect(screen.getByLabelText("Live data: Live")).toBeInTheDocument();
});

it("explains why no index is shown", () => {
  renderUi(
    <LiveIndices
      live={{ connection: "reconnecting", indices: [], companies: new Map(), status: null }}
    />,
  );
  expect(screen.getByText(/Reconnecting to the live feed/)).toBeInTheDocument();
});

it("shows the company quote, order pressure and depth", () => {
  renderUi(<LiveCompanyQuote quote={equity} connection="live" status={status} />);
  expect(screen.getByText("INR 101.25")).toBeInTheDocument();
  expect(screen.getByText("12,345")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Buy orders 75\.00%/ })).toBeInTheDocument();
  const depth = screen.getByRole("table", { name: "Market depth (top 5)" });
  expect(within(depth).getByText("101.20")).toBeInTheDocument();
  expect(screen.getByText(/Last trade \(delayed\)/)).toBeInTheDocument();
});
