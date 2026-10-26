import { describe, expect, it } from "vitest";
import type { CompanyBar, CompanySignal, CompanyStory } from "../../shared/api/generated/types.gen";
import {
  moveDirection,
  newsInWindow,
  outlookResults,
  projectClosingPrices,
  projectionResults,
  projectionSummary,
  sessionClose,
} from "./predictionAnalysis";

const now = Date.parse("2026-10-26T12:00:00Z");
function history(length = 60): CompanyBar[] {
  return Array.from({ length }, (_, index) => ({
    day: new Date(Date.UTC(2026, 7, 1 + index)).toISOString().slice(0, 10),
    open: 100 + index,
    high: 102 + index,
    low: 99 + index,
    close: 100 + index,
    volume: 1000,
  }));
}
const signal: CompanySignal = {
  target_date: "2026-09-01",
  direction: "up",
  score: 0.5,
  momentum_score: 0.6,
  news_score: 0.3,
  created_at: "2026-08-31T12:00:00Z",
  inputs: { close: 100, price_as_of: "2026-08-31", momentum_weight: 0.7, news_weight: 0.3 },
};
const actual: CompanyBar = {
  day: "2026-09-01",
  open: 100,
  high: 103,
  low: 99,
  close: 102,
  volume: 100,
};

describe("chart projection historical verification", () => {
  it.each([1, 5, 20])(
    "exactly reconstructs the chart algorithm at each %i-session horizon",
    (horizon) => {
      const candles = history();
      const results = projectionResults(candles, horizon, now);
      expect(results).toHaveLength(60 - 19 - horizon);
      for (const result of results) {
        expect(result.predicted).toBe(result.target.close);
        const cutoff = candles.findIndex((bar) => bar.day === result.origin.day);
        expect(result.predicted).toBe(
          projectClosingPrices(candles.slice(0, cutoff + 1))[horizon].value,
        );
      }
      expect(projectionSummary(results)).toMatchObject({
        mae: 0,
        rmse: 0,
        mape: 0,
        directionAccuracy: 100,
        baselineMae: horizon,
      });
    },
  );

  it("does not leak future prices into the fit or hide a reversal", () => {
    const candles = history(25);
    const before = projectionResults(candles, 5, now)[0];
    candles[24] = { ...candles[24], close: 90 };
    const after = projectionResults(candles, 5, now)[0];
    expect(after.predicted).toBe(before.predicted);
    expect(after.error).toBe(-34);
    expect(after.actualMove).toBeLessThan(0);
    expect(after.projectedMove).toBeGreaterThan(0);
    expect(after.matched).toBe(false);
    expect(projectionSummary([after])).toMatchObject({
      mae: 34,
      rmse: 34,
      baselineMae: 29,
      directionAccuracy: 0,
      bias: -34,
    });
    expect(projectionSummary([after])!.mape).toBeCloseTo((34 / 90) * 100);
  });

  it("does not score incomplete target sessions, invalid prices or insufficient history", () => {
    const candles = history(21);
    const close = sessionClose(candles.at(-1)!.day);
    expect(projectionResults(candles, 1, close - 1)).toEqual([]);
    expect(projectionResults(candles, 1, close)).toHaveLength(1);
    expect(projectionResults(candles.slice(0, 20), 1, now)).toEqual([]);
    expect(projectionResults(candles, 7, now)).toEqual([]);
    expect(projectionSummary([])).toBeNull();
    expect(projectClosingPrices(candles.map((bar) => ({ ...bar, close: 0 })))).toEqual([]);
    expect(
      projectionResults(
        candles.map((bar) => ({ ...bar, close: Number.NaN })),
        1,
        now,
      ),
    ).toEqual([]);
    expect(projectionResults([...candles].reverse(), 1, now)).toEqual([]);
    expect(
      projectionResults(
        candles.map((bar) => ({ ...bar, day: "invalid" })),
        1,
        now,
      ),
    ).toEqual([]);
  });

  it("uses the same +/-0.5% flat convention and caps the sample at 60 outcomes", () => {
    expect(moveDirection(0)).toBe("flat");
    expect(moveDirection(0.5)).toBe("flat");
    expect(moveDirection(-0.5)).toBe("flat");
    expect(moveDirection(0.5001)).toBe("up");
    expect(moveDirection(-0.5001)).toBe("down");
    expect(projectionResults(history(80), 1, now)).toHaveLength(60);
  });
});

describe("saved outlook verification", () => {
  it("checks direction, not a fabricated price target, and preserves saved inputs", () => {
    const [result] = outlookResults([signal], [actual], now);
    expect(result).toMatchObject({
      state: "Matched",
      actualClose: 102,
      actualMove: expect.closeTo(2),
    });
    expect(result.signal).toBe(signal);
    expect(outlookResults([{ ...signal, direction: "down" }], [actual], now)[0].state).toBe(
      "Missed",
    );
    expect(
      outlookResults([{ ...signal, direction: "flat" }], [{ ...actual, close: 100.3 }], now)[0]
        .state,
    ).toBe("Matched");
  });

  it("uses the earliest saved outlook per target, not a favorable later revision", () => {
    const later = { ...signal, created_at: "2026-09-01T03:00:00Z", direction: "down" };
    const results = outlookResults([later, signal], [actual], now);
    expect(results).toHaveLength(1);
    expect(results[0].signal).toBe(signal);
  });

  it("orders issuance by timestamp rather than by the text of its timezone offset", () => {
    const earlier = { ...signal, created_at: "2026-08-31T13:15:00+02:00", direction: "down" };
    const results = outlookResults([signal, earlier], [actual], now);
    expect(results[0].signal).toBe(earlier);
    expect(results[0].state).toBe("Missed");
  });

  it.each([99.5, 100.5])(
    "keeps an exact flat-band boundary close %s flat despite floating-point rounding",
    (close) => {
      expect(
        outlookResults([{ ...signal, direction: "flat" }], [{ ...actual, close }], now)[0].state,
      ).toBe("Matched");
    },
  );

  it("does not score pending predictions or replace a missing target with a later close", () => {
    expect(outlookResults([signal], [actual], sessionClose(signal.target_date) - 1)[0].state).toBe(
      "Pending",
    );
    expect(outlookResults([signal], [{ ...actual, day: "2026-09-02" }], now)[0].state).toBe(
      "Not verifiable",
    );
    expect(outlookResults([signal], [{ ...actual, close: 0 }], now)[0].state).toBe(
      "Not verifiable",
    );
  });

  it.each([
    { ...signal, created_at: "2026-09-01T03:45:00Z" },
    { ...signal, created_at: "2026-08-31T09:00:00Z" },
    { ...signal, inputs: {} },
    { ...signal, inputs: { ...signal.inputs, close: -1 } },
    { ...signal, inputs: { ...signal.inputs, price_as_of: "2026-09-01" } },
    { ...signal, created_at: "invalid" },
    { ...signal, direction: "unknown" },
  ])("excludes hindsight-created or incomplete evidence", (invalid) => {
    expect(outlookResults([invalid], [actual], now)[0].state).toBe("Not verifiable");
  });
});

it("links only timestamped news after cutoff and no later than the realized target close", () => {
  const story: CompanyStory = {
    title: "Earnings announcement",
    url: "https://example.test/news",
    source: "Wire",
    published_at: "2026-09-01T06:00:00Z",
    sentiment_score: -0.6,
    relevance: 0.9,
    sentiment_reason: "Weak earnings",
  };
  const before = { ...story, published_at: "2026-08-31T09:59:59Z" };
  const after = { ...story, published_at: "2026-09-01T10:00:01Z" };
  const atEnd = { ...story, published_at: "2026-09-01T10:00:00Z" };
  const atCutoff = { ...story, published_at: "2026-08-31T10:00:00Z" };
  const undated = { ...story, published_at: null };
  const invalid = { ...story, published_at: "invalid" };
  expect(
    newsInWindow(
      [after, atEnd, before, story, undated, atCutoff, invalid],
      sessionClose("2026-08-31"),
      sessionClose("2026-09-01"),
    ),
  ).toEqual([story, atEnd]);
});
