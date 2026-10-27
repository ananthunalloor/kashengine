import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ThemeProvider } from "../../app/ThemeProvider";
import type { CompanyBar } from "../../shared/api/generated/types.gen";
import { CompanyTradeSetups, tradeEvidence } from "./CompanyTradeSetups";

function history(length = 60): CompanyBar[] {
  return Array.from({ length }, (_, index) => ({
    day: new Date(Date.UTC(2026, 7, 28 + index)).toISOString().slice(0, 10),
    open: 100 + index,
    high: 103 + index,
    low: 99 + index,
    close: 102 + index,
    volume: index === length - 1 ? 1000 : 100,
  }));
}
afterEach(() => vi.useRealTimers());

function show(candles: CompanyBar[]) {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
  render(
    <ThemeProvider>
      <CompanyTradeSetups candles={candles} />
    </ThemeProvider>,
  );
}

it("derives evidence from prior sessions and calculates exact illustrative 2R risk", () => {
  const evidence = tradeEvidence(history())!;
  expect(evidence.last.day).toBe("2026-10-26");
  expect(evidence.support).toBe(138);
  expect(evidence.resistance).toBe(161);
  expect(evidence.risk).toBe(23);
  expect(evidence.resistance + 2 * evidence.risk).toBe(207);
  expect(evidence.sma20).toBe(151.5);
  expect(evidence.sma50).toBe(136.5);
  expect(evidence.volumeConfirmed).toBe(true);
  show(history());
  expect(screen.getByText("Watch for confirmation")).toBeInTheDocument();
  expect(screen.getByText("Trend-aligned watch")).toBeInTheDocument();
  expect(screen.getByText(/At an assumed entry of INR 161/)).toHaveTextContent(
    "2R scenario is INR 207",
  );
  expect(screen.getByText("Not assessable")).toBeInTheDocument();
});

it("does not generate levels from missing, invalid or flat-range candles", () => {
  expect(tradeEvidence(history(20))).toBeNull();
  expect(tradeEvidence(history().map((bar) => ({ ...bar, high: bar.low - 1 })))).toBeNull();
  expect(tradeEvidence(history().map((bar) => ({ ...bar, close: Number.NaN })))).toBeNull();
  expect(
    tradeEvidence(history().map((bar) => ({ ...bar, open: 100, high: 100, low: 100, close: 100 }))),
  ).toBeNull();
  show([]);
  expect(screen.getByText("Wait / insufficient data")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("requires more history for positional setups and waits on stale observations", () => {
  show(history(30));
  expect(screen.getByRole("alert", { name: "Wait / stale history" })).toBeInTheDocument();
  expect(screen.getByText("Wait / no long setup")).toBeInTheDocument();
  expect(screen.queryByText("Watch for confirmation")).not.toBeInTheDocument();
});

it("needs 50 sessions for positional analysis even when recent short-term history is available", () => {
  show(history().slice(-30));
  expect(screen.getByText("Need 50 sessions")).toBeInTheDocument();
  expect(screen.getByText("Watch for confirmation")).toBeInTheDocument();
});

it("waits on weak momentum rather than turning it into a short recommendation", () => {
  const candles = history().map((bar, index) => ({
    ...bar,
    open: 200 - index,
    high: 203 - index,
    low: 199 - index,
    close: 202 - index,
  }));
  show(candles);
  expect(screen.getByText("Wait / no long setup")).toBeInTheDocument();
  expect(screen.getByText("Wait / trend not aligned")).toBeInTheDocument();
});
