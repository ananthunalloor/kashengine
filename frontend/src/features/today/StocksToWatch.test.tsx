import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { ThemeProvider } from "../../app/ThemeProvider";
import type { StocksWatch } from "../../shared/api/generated/types.gen";
import { StocksToWatch } from "./StocksToWatch";

const watch: StocksWatch = {
  as_of: "2026-10-26T04:30:00Z",
  since: "2026-10-24T16:30:00Z",
  session_date: "2026-10-26",
  next_session: "2026-10-26",
  session_state: "open",
  sampled_articles: 1,
  truncated: false,
  items: [
    {
      id: 7,
      name: "Example Industries",
      symbol: "EXAMPLE",
      sector: "Energy",
      bias: "bullish",
      score: 0.8,
      attention: 0.72,
      articles: 1,
      sources: 1,
      positive: 1,
      negative: 0,
      latest_news_at: "2026-10-26T03:30:00Z",
      stories: [
        {
          title: "Strong earnings",
          url: "https://example.test/earnings",
          source: "Wire",
          published_at: "2026-10-26T03:30:00Z",
          sentiment_score: 0.8,
          relevance: 0.9,
          sentiment_reason: "Earnings improved; company-linked news context.",
        },
      ],
    },
  ],
};

function show(data = watch) {
  render(
    <ThemeProvider>
      <StocksToWatch data={data} />
    </ThemeProvider>,
  );
}

it("shows a dated company watch, directional bias and linked evidence without price forecasts", () => {
  show();
  expect(screen.getByRole("heading", { name: "Stocks to watch today" })).toBeInTheDocument();
  const company = within(screen.getByRole("article", { name: "EXAMPLE news watch" }));
  expect(company.getByRole("link", { name: "Example Industries" })).toHaveAttribute(
    "href",
    "/companies/7/",
  );
  expect(company.getByText("Bullish news bias")).toBeInTheDocument();
  expect(company.getByText(/upward pressure is possible, not assured/)).toBeInTheDocument();
  expect(company.getByText("Single-article evidence")).toBeInTheDocument();
  expect(company.getByRole("link", { name: /Strong earnings/ })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  expect(company.getByText(/Earnings improved/)).toBeInTheDocument();
  expect(company.getByText(/News balance \+0.8/)).toHaveTextContent("Not a probability");
  expect(screen.getByText(/not a live feed/)).toBeInTheDocument();
  expect(screen.getByText(/not necessarily its impact on every company/)).toBeInTheDocument();
});

it.each([
  ["bearish", "Bearish news bias", "downward pressure"],
  ["mixed", "Mixed news", "No clear directional view"],
  ["neutral", "No clear news edge", "does not support a clear direction"],
] as const)(
  "renders %s evidence without overstating the expected move",
  (bias, label, explanation) => {
    show({ ...watch, items: [{ ...watch.items[0], bias }] });
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(explanation))).toBeInTheDocument();
  },
);

it("does not make unsafe news URLs clickable and renders titles as text", () => {
  show({
    ...watch,
    items: [
      {
        ...watch.items[0],
        stories: [
          {
            ...watch.items[0].stories[0],
            title: "<b>Unsafe story</b>",
            url: "javascript:alert(1)",
          },
        ],
      },
    ],
  });
  expect(screen.getByText("<b>Unsafe story</b>")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Unsafe story/ })).not.toBeInTheDocument();
  expect(document.querySelector("b")).toBeNull();
});

it.each(["closed", "ended"] as const)(
  "does not show movement calls when the session is %s",
  (session_state) => {
    show({ ...watch, session_state, next_session: "2026-10-27" });
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.getByText(/Next scheduled session/)).toHaveTextContent(
      "Tuesday, 27 October 2026",
    );
    expect(screen.getByText(/No today's-movement calls/)).toBeInTheDocument();
  },
);

it("shows missing evidence rather than inferring a movement and exposes sampling limits", () => {
  show({ ...watch, items: [], truncated: true, sampled_articles: 300 });
  expect(screen.getByText("No news-backed stocks to watch yet")).toBeInTheDocument();
  expect(screen.getByText(/No direction is guessed/)).toBeInTheDocument();
  expect(screen.getByText(/coverage limited to the latest 300/)).toBeInTheDocument();
});

it("keeps calculation rules collapsed but available on request", async () => {
  show();
  const control = screen.getByRole("button", { name: /Why these stocks/ });
  expect(control).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(control);
  await waitFor(() =>
    expect(screen.getByText(/relevance-weighted average sentiment/)).toBeVisible(),
  );
  expect(screen.getByText(/has not been backtested/)).toBeVisible();
});
