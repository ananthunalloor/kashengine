import { Group, Text, Tooltip } from "@mantine/core";
import type { ReactNode } from "react";

import { directionGlyph, directionOf, formatPercent, formatSigned } from "./format";
import type { Direction } from "./format";

export type Tone = "gain" | "loss" | "caution" | "info" | "brand" | "neutral" | "outline";

/** Pill used for every status in v2. Tone is semantic; the text always carries the meaning too. */
export function StatusBadge({
  tone = "neutral",
  children,
  dot = false,
  pulse = false,
  size = "sm",
  icon,
}: {
  tone?: Tone;
  children: ReactNode;
  dot?: boolean;
  pulse?: boolean;
  size?: "xs" | "sm";
  icon?: ReactNode;
}) {
  return (
    <span className="kv2-tone" data-tone={tone} data-size={size}>
      {dot ? <span className="kv2-dot" data-pulse={pulse} /> : null}
      {icon}
      {children}
    </span>
  );
}

const directionTone: Record<Direction, Tone> = { up: "gain", down: "loss", flat: "neutral" };
const directionClass: Record<Direction, string> = {
  up: "kv2-gain",
  down: "kv2-loss",
  flat: "kv2-flat",
};

/** Coloured change value with ▲ / ▼ / – glyph. `kind="percent"` appends %. */
export function Delta({
  value,
  kind = "percent",
  decimals = 2,
  fw = 500,
  size = "sm",
}: {
  value: number | null | undefined;
  kind?: "percent" | "points";
  decimals?: number;
  fw?: number;
  size?: "xs" | "sm" | "md";
}) {
  const dir = directionOf(value);
  const text =
    kind === "percent" ? formatPercent(value, { decimals }) : formatSigned(value, decimals);
  return (
    <Text component="span" size={size} fw={fw} className={`kv2-num ${directionClass[dir]}`}>
      {directionGlyph[dir]} {text}
    </Text>
  );
}

/** "▲ RISE" style badge for a predicted or observed direction. */
export function DirectionBadge({
  direction,
  label,
  size = "sm",
}: {
  direction: Direction;
  label?: string;
  size?: "xs" | "sm";
}) {
  const fallback = { up: "Rise", down: "Fall", flat: "Flat" }[direction];
  return (
    <StatusBadge tone={directionTone[direction]} size={size}>
      {directionGlyph[direction]} {label ?? fallback}
    </StatusBadge>
  );
}

/** Sentiment pill for a −1..+1 score. */
export function SentimentPill({ score, size = "sm" }: { score: number; size?: "xs" | "sm" }) {
  const dir = directionOf(score, 0.15);
  const label = { up: "Positive", down: "Negative", flat: "Neutral" }[dir];
  return (
    <StatusBadge tone={directionTone[dir]} size={size}>
      {directionGlyph[dir]} {label} {formatSigned(score)}
    </StatusBadge>
  );
}

/** 5-segment strength meter for a 0–10 score. */
export function StrengthMeter({
  score,
  max = 10,
  tone = "brand",
  showValue = true,
  label,
}: {
  score: number;
  max?: number;
  tone?: "brand" | "gain" | "loss" | "caution";
  showValue?: boolean;
  label?: string;
}) {
  const on = Math.round((score / max) * 5);
  const colour = tone === "brand" ? "var(--kv2-brand)" : `var(--kv2-${tone})`;
  const word = label ?? (on >= 4 ? "Strong" : on >= 3 ? "Moderate" : "Weak");
  return (
    <Group gap={8} wrap="nowrap">
      <span
        className="kv2-strength"
        style={{ color: colour }}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={score}
        aria-label={`Strength ${score} of ${max}`}
      >
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} data-on={i < on} />
        ))}
      </span>
      {showValue ? (
        <Text size="xs" fw={600} className="kv2-num" style={{ whiteSpace: "nowrap" }}>
          {score.toFixed(1)} / {max} · {word}
        </Text>
      ) : null}
    </Group>
  );
}

/** Diverging bar for a −1..+1 score, centred on zero. */
export function ScoreBar({ score, width = 96 }: { score: number; width?: number }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pct = Math.abs(clamped) * 50;
  const positive = clamped >= 0;
  return (
    <Tooltip label={`Score ${formatSigned(clamped)}`}>
      <div className="kv2-scorebar" style={{ width }} aria-label={`Score ${formatSigned(clamped)}`}>
        <span
          style={{
            left: positive ? "50%" : `${50 - pct}%`,
            width: `${pct}%`,
            background: positive ? "var(--kv2-gain)" : "var(--kv2-loss)",
          }}
        />
      </div>
    </Tooltip>
  );
}

export type Freshness = "live" | "delayed" | "stale" | "closed";

/** Freshness of a data feed: live (pulsing), delayed, stale, closed. */
export function FreshnessTag({ state, detail }: { state: Freshness; detail?: string }) {
  const map: Record<Freshness, { tone: Tone; label: string }> = {
    live: { tone: "gain", label: "Live" },
    delayed: { tone: "caution", label: "Delayed" },
    stale: { tone: "loss", label: "Stale" },
    closed: { tone: "neutral", label: "Closed" },
  };
  const { tone, label } = map[state];
  return (
    <StatusBadge tone={tone} dot pulse={state === "live"} size="xs">
      {label}
      {detail ? ` · ${detail}` : ""}
    </StatusBadge>
  );
}

/** "NSE: SMPL" chip. */
export function SymbolChip({ symbol, exchange = "NSE" }: { symbol: string; exchange?: string }) {
  return (
    <StatusBadge tone="outline" size="xs">
      <span className="kv2-mono">
        {exchange}: {symbol}
      </span>
    </StatusBadge>
  );
}
