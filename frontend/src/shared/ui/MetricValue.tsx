import type { ReactNode } from "react";

import { displayNumber } from "./displayNumber";

type MetricKind = "change" | "strength" | "score";

export function MetricValue({
  value,
  kind,
  children,
}: {
  value: string | null;
  kind: MetricKind;
  children?: ReactNode;
}) {
  const number = value === null ? null : displayNumber(value);
  const available = number !== null && (kind === "change" || (number >= 1 && number <= 10));
  let tone = "neutral";
  let meaning = "Not available";
  if (available) {
    if (kind === "strength") {
      tone = number >= 6.4 ? "positive" : "caution";
      meaning = number >= 6.4 ? "Strong signal" : "Lower strength";
    } else {
      const midpoint = kind === "score" ? 5.5 : 0;
      tone = number > midpoint ? "positive" : number < midpoint ? "negative" : "neutral";
      meaning = number > midpoint ? "Positive" : number < midpoint ? "Negative" : "Neutral";
    }
  }
  return (
    <span className="metric-value" data-metric={kind} data-tone={tone} title={meaning}>
      {children ?? value ?? "\u2013"}
    </span>
  );
}

export function StrengthLegend() {
  return (
    <span className="metric-legend">
      <span className="metric-value" data-tone="positive">
        Strong: 6.4-10.0
      </span>
      {" / "}
      <span className="metric-value" data-tone="caution">
        Lower strength: 1.0-6.3
      </span>
      . Strength is not market direction or a probability.
    </span>
  );
}
