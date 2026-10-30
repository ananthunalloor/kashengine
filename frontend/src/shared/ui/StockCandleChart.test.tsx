import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ThemeProvider } from "../../app/ThemeProvider";
import { movingAverage, StockCandleChart } from "./StockCandleChart";

const candles = Array.from({ length: 130 }, (_, index) => ({
  label: `Session ${index + 1}`,
  open: 100 + index,
  high: 103 + index,
  low: 99 + index,
  close: 102 + index,
  volume: 1000 + index,
}));

function show() {
  return render(
    <ThemeProvider>
      <StockCandleChart
        candles={candles}
        projectionPoints={[
          { label: "Session 130", value: 231 },
          ...Array.from({ length: 20 }, (_, index) => ({
            label: `T+${index + 1}`,
            value: 232 + index,
          })),
        ]}
        ariaLabel="Daily candlestick chart"
      />
    </ThemeProvider>,
  );
}

it("shows a larger chart and exact OHLCV on pointer, touch and keyboard inspection", () => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  const { container } = show();
  const chart = screen.getByRole("img");
  expect(chart).toHaveAttribute("height", "440");
  const hitArea = container.querySelector(".stock-chart-hit-area")!;
  // Default window starts at session 71; 80 slots include the 20 projected sessions.
  fireEvent.pointerMove(hitArea, { clientX: 16 });
  const readout = screen.getByLabelText("Selected chart values");
  expect(readout).toHaveTextContent("Session 71");
  expect(readout).toHaveTextContent("O 170 · H 173 · L 169 · C 172 INR | Volume 1,070");
  expect(container.querySelector(".stock-chart-crosshair")).toBeInTheDocument();
  fireEvent.keyDown(chart, { key: "ArrowRight" });
  expect(readout).toHaveTextContent("Session 72");
  fireEvent.pointerLeave(hitArea);
  expect(readout).toHaveTextContent("Session 130");
  fireEvent.pointerDown(hitArea, { clientX: 16 });
  fireEvent.pointerUp(hitArea);
  expect(readout).toHaveTextContent("Session 71");
  fireEvent.keyDown(chart, { key: "Escape" });
  expect(container.querySelector(".stock-chart-crosshair")).not.toBeInTheDocument();
});

it("supports ranges, zoom, panning, reset and projection hover without inventing OHLCV", () => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  const { container } = show();
  const count = () => container.querySelectorAll("[data-candle]").length;
  expect(count()).toBe(60);
  fireEvent.click(screen.getByRole("button", { name: "1M" }));
  expect(count()).toBe(20);
  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(count()).toBe(14);
  fireEvent.click(screen.getByRole("button", { name: "Earlier" }));
  expect(container.querySelector("[data-candle='Session 130']")).toBeNull();
  expect(screen.getByRole("img")).not.toHaveAccessibleName(/followed by/);
  fireEvent.click(screen.getByRole("button", { name: "Later" }));
  expect(container.querySelector("[data-candle='Session 130']")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "All" }));
  expect(count()).toBe(130);
  fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
  expect(count()).toBe(60);
  fireEvent.pointerMove(container.querySelector(".stock-chart-hit-area")!, { clientX: 816 });
  expect(screen.getByLabelText("Selected chart values")).toHaveTextContent(
    "T+20 | Illustrative projection: INR 251",
  );
  expect(screen.getByLabelText("Selected chart values")).not.toHaveTextContent("Volume");
  fireEvent.click(screen.getByRole("checkbox", { name: "Projection" }));
  expect(screen.queryByLabelText("History-only projection")).not.toBeInTheDocument();
});

it("pans by dragging and keyboard without exceeding available history", () => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  const { container } = show();
  const area = container.querySelector(".stock-chart-hit-area")!;
  fireEvent.pointerDown(area, { clientX: 100 });
  fireEvent.pointerMove(area, { clientX: 200 });
  fireEvent.pointerUp(area);
  expect(container.querySelector("[data-candle='Session 130']")).toBeNull();
  fireEvent.keyDown(screen.getByRole("img"), { key: "ArrowLeft", shiftKey: true });
  expect(screen.getByRole("button", { name: "Later" })).toBeEnabled();
  for (let i = 0; i < 12; i++) fireEvent.click(screen.getByRole("button", { name: "Earlier" }));
  expect(screen.getByRole("button", { name: "Earlier" })).toBeDisabled();
  expect(container.querySelector("[data-candle='Session 1']")).toBeInTheDocument();
});

it("computes averages from full history, toggles indicators and enters/exits fullscreen", () => {
  const { container } = show();
  expect(movingAverage(candles, 18, 20)).toBeNull();
  expect(movingAverage(candles, 19, 20)).toBe(111.5);
  fireEvent.click(screen.getByRole("button", { name: "1M" }));
  fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
  expect(screen.getByLabelText("Selected chart values")).toHaveTextContent("SMA 20: 221.5");
  fireEvent.click(screen.getByRole("checkbox", { name: "SMA 50" }));
  expect(screen.getByLabelText("Selected chart values")).toHaveTextContent("SMA 50: 206.5");
  fireEvent.click(screen.getByRole("checkbox", { name: "Volume" }));
  expect(container.querySelector("[data-volume]")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Fullscreen" }));
  expect(screen.getByRole("dialog", { name: "Daily price chart" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Exit fullscreen" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("does not draw a projection without observed candles to anchor it", () => {
  render(
    <ThemeProvider>
      <StockCandleChart
        candles={[]}
        projectionPoints={[
          { label: "T+0", value: 100 },
          { label: "T+1", value: 101 },
        ]}
        ariaLabel="Empty daily chart"
      />
    </ThemeProvider>,
  );
  expect(screen.getByLabelText("Selected chart values")).toHaveTextContent("No saved candles.");
  expect(screen.queryByLabelText("History-only projection")).not.toBeInTheDocument();
});

it("renders company history and its projection in muted gray", () => {
  const { container } = render(
    <ThemeProvider>
      <StockCandleChart
        candles={candles}
        projectionPoints={[
          { label: "Session 130", value: 231 },
          { label: "T+1", value: 232 },
        ]}
        muted
        ariaLabel="Muted company price chart"
      />
    </ThemeProvider>,
  );
  expect(container.querySelector("[data-candle] line")).toHaveAttribute("stroke", "#858b92");
  expect(container.querySelector('[aria-label="20-session moving average"]')).toHaveAttribute(
    "stroke",
    "#858b92",
  );
  expect(container.querySelector('[aria-label="History-only projection"]')).toHaveAttribute(
    "stroke",
    "#858b92",
  );
});
