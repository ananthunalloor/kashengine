import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { CompanyDetail } from "../../shared/api/generated/types.gen";
import { ThemeProvider } from "../../app/ThemeProvider";
import { PredictionReview } from "./PredictionReview";

afterEach(() => vi.restoreAllMocks());
function detail(): CompanyDetail {
  return {
    company: {
      id: 1,
      name: "Example",
      symbol: "EX",
      listings: [],
      sector: "",
      screener_url: "",
      last_updated: null,
    },
    summary: "",
    instrument_key: "KEY",
    fundamentals: {},
    fundamentals_source: "",
    fundamentals_as_of: null,
    errors: {},
    markets_available: true,
    news_available: true,
    ipos_available: false,
    quote: null,
    outlook: null,
    candles: Array.from({ length: 25 }, (_, index) => ({
      day: new Date(Date.UTC(2026, 8, 1 + index)).toISOString().slice(0, 10),
      open: 100 + index,
      high: 102 + index,
      low: 99 + index,
      close: index === 24 ? 90 : 100 + index,
      volume: 100,
    })),
    outlook_history: [
      {
        target_date: "2026-09-25",
        direction: "up",
        score: 0.51,
        momentum_score: 0.6,
        news_score: 0.3,
        created_at: "2026-09-24T11:00:00Z",
        inputs: {
          price_as_of: "2026-09-24",
          close: 123,
          momentum_weight: 0.7,
          news_weight: 0.3,
          method: "momentum-news-v1",
        },
      },
    ],
    news: [
      {
        title: "Earnings miss",
        url: "https://example.test/earnings",
        source: "Wire",
        published_at: "2026-09-25T06:00:00Z",
        sentiment_score: -0.6,
        relevance: 0.9,
        sentiment_reason: "Profit fell",
      },
      {
        title: "Unsafe link story",
        url: "javascript:alert(1)",
        source: "Wire",
        published_at: "2026-09-25T06:30:00Z",
        sentiment_score: null,
        relevance: null,
        sentiment_reason: "",
      },
      {
        title: "Later story",
        url: "https://example.test/later",
        source: "Wire",
        published_at: "2026-09-26T06:00:00Z",
        sentiment_score: null,
        relevance: null,
        sentiment_reason: "",
      },
    ],
    ipos: [],
  };
}
function show(data = detail()) {
  vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-26T12:00:00Z"));
  render(
    <ThemeProvider>
      <PredictionReview data={data} />
    </ThemeProvider>,
  );
}

it("shows measurable errors and in-window news links without asserting causality", async () => {
  show();
  expect(
    screen.getByRole("heading", { name: "Prediction accuracy & deviations" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Projection accuracy summary")).toHaveTextContent(
    "Average price missINR 6.8",
  );
  expect(screen.getByLabelText("Projection accuracy summary")).toHaveTextContent(
    "Direction correct80%",
  );
  expect(screen.getByLabelText("Saved outlook summary")).toHaveTextContent(
    "0 of 1 completed outlooks matched",
  );
  expect(
    screen.getByRole("heading", { name: "Latest direction miss · 2026-09-25" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Actual finished INR 34 below the projection.", { exact: false }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Earnings miss/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /How we check predictions/ })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  fireEvent.click(screen.getByRole("button", { name: /Projection deviations & news/ }));
  const table = within(await screen.findByRole("table", { name: "Projection deviations" }));
  const missed = table.getByRole("row", { name: /Direction missed/ });
  expect(missed).toHaveTextContent("-34 INR");
  expect(missed).toHaveTextContent("Price moved against the fitted trend");
  expect(within(missed).getByRole("link", { name: /Earnings miss/ })).toHaveAttribute(
    "href",
    "https://example.test/earnings",
  );
  expect(within(missed).queryByRole("link", { name: /Unsafe link story/ })).not.toBeInTheDocument();
  expect(table.queryByText("Later story")).not.toBeInTheDocument();
  expect(within(missed).getByText(/possible context, not proven cause/)).toBeInTheDocument();
});

it("explains the saved model inputs and outcome separately from price projection errors", async () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: /Saved outlook results & news/ }));
  const table = within(await screen.findByRole("table", { name: "Saved outlook verification" }));
  expect(table.getByText("Missed")).toBeInTheDocument();
  expect(table.getByText(/weighted contribution \+0.42/)).toHaveTextContent(
    "news score 0.3 (weighted contribution +0.09)",
  );
  expect(table.getByText(/specific cause cannot be determined/)).toBeInTheDocument();
  expect(table.getByRole("link", { name: /Earnings miss/ })).toBeInTheDocument();
});

it("changes horizons without reusing a different sample or inventing accuracy", () => {
  show();
  fireEvent.change(screen.getByRole("combobox", { name: "Forecast horizon" }), {
    target: { value: "5" },
  });
  expect(screen.getByText(/Based on 1 historical comparison/)).toBeInTheDocument();
  expect(screen.getByLabelText("Projection accuracy summary")).toHaveTextContent(
    "Average price missINR 34",
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Forecast horizon" }), {
    target: { value: "20" },
  });
  expect(screen.getByText(/need at least 40 valid saved daily closes/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Projection accuracy summary")).not.toBeInTheDocument();
});

it("does not imply no news means no event, and explains unavailable news access", async () => {
  show({ ...detail(), news_available: false, news: [], outlook_history: [] });
  fireEvent.click(screen.getByRole("button", { name: /Projection deviations & news/ }));
  expect(screen.getAllByText("News context requires News access.").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: /How we check predictions/ }));
  expect(await screen.findByText(/No matching news does not mean no event occurred/)).toBeVisible();
  expect(screen.getByText(/verification requires News access/)).toBeInTheDocument();
});

it("keeps methodology and full histories collapsed until requested", async () => {
  show();
  expect(screen.getByRole("button", { name: /How we check predictions/ })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(screen.getByRole("button", { name: /Projection deviations & news/ })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(screen.getByRole("button", { name: /Saved outlook results & news/ })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  fireEvent.click(screen.getByRole("button", { name: /How we check predictions/ }));
  expect(await screen.findByText(/Additional metrics:/)).toBeVisible();
  expect(screen.getByText(/A correct direction can still have a large price miss/)).toBeVisible();
});

it("does not show a favorable verdict when the model underperforms a no-change guess", () => {
  const data = detail();
  data.candles[24].close = 90;
  data.candles = data.candles.slice(0, 20).concat(data.candles[24]);
  show(data);
  expect(
    screen.getByRole("alert", { name: "Higher price error than a no-change guess" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Projection accuracy summary")).toHaveTextContent(
    "Average price missINR 30",
  );
});
