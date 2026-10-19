import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { MetricValue, StrengthLegend } from "./MetricValue";

it.each([
  ["+1.25%", "positive", "Positive"],
  ["\u22121.25%", "negative", "Negative"],
  ["-1.25%", "negative", "Negative"],
  ["+1,234.5", "positive", "Positive"],
  ["0.00%", "neutral", "Neutral"],
  ["-0.00%", "neutral", "Neutral"],
  ["\u2013", "neutral", "Not available"],
  ["-", "neutral", "Not available"],
  [null, "neutral", "Not available"],
])("colors change %s while preserving its sign and units", (value, tone, title) => {
  render(<MetricValue kind="change" value={value} />);
  const metric = screen.getByTitle(title);
  expect(metric).toHaveAttribute("data-tone", tone);
  expect(metric).toHaveTextContent(value ?? "\u2013");
});

it.each([
  ["1.0/10", "caution", "Lower strength"],
  ["6.3/10", "caution", "Lower strength"],
  ["6.4/10", "positive", "Strong signal"],
  ["10.0/10", "positive", "Strong signal"],
  ["-", "neutral", "Not available"],
  ["0.0/10", "neutral", "Not available"],
  ["11.0/10", "neutral", "Not available"],
])("uses the existing strong-signal cutoff for strength %s", (value, tone, title) => {
  render(<MetricValue kind="strength" value={value} />);
  expect(screen.getByTitle(title)).toHaveAttribute("data-tone", tone);
});

it.each([
  ["1.0/10", "negative", "Negative"],
  ["5.4/10", "negative", "Negative"],
  ["5.5/10", "neutral", "Neutral"],
  ["5.6/10", "positive", "Positive"],
  ["10.0/10", "positive", "Positive"],
  [null, "neutral", "Not available"],
])("uses 5.5 as the neutral midpoint for score %s", (value, tone, title) => {
  render(<MetricValue kind="score" value={value} />);
  expect(screen.getByTitle(title)).toHaveAttribute("data-tone", tone);
});

it("keeps the full fact text and freshness without interpreting it as HTML", () => {
  render(
    <MetricValue kind="change" value="-20">
      {"\u20b9-20 (-20.0%) (updated 3 days ago) <b>saved</b>"}
    </MetricValue>,
  );
  expect(screen.getByTitle("Negative")).toHaveTextContent("updated 3 days ago");
  expect(screen.getByTitle("Negative")).toHaveTextContent("<b>saved</b>");
  expect(document.querySelector("b")).toBeNull();
});

it("explains strength colors in words, separately from market direction", () => {
  render(<StrengthLegend />);
  expect(screen.getByText("Strong: 6.4-10.0")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("Lower strength: 1.0-6.3")).toHaveAttribute("data-tone", "caution");
  expect(screen.getByText(/not market direction or a probability/)).toBeInTheDocument();
});
