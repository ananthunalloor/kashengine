import type { CompanyBar, CompanySignal, CompanyStory } from "../../shared/api/generated/types.gen";

export const projectionWindow = 20;
export const flatMovePercent = 0.5;
export const sessionClose = (day: string) => Date.parse(`${day}T15:30:00+05:30`);

export function projectClosingPrices(candles: CompanyBar[]): { label: string; value: number }[] {
  if (candles.length < projectionWindow) return [];
  const history = candles.slice(-projectionWindow);
  if (
    history.some(
      (bar, index) =>
        !Number.isFinite(bar.close) ||
        bar.close <= 0 ||
        !Number.isFinite(sessionClose(bar.day)) ||
        (index > 0 && bar.day <= history[index - 1].day),
    )
  )
    return [];
  const closes = history.map((bar) => bar.close);
  const meanX = (closes.length - 1) / 2;
  const meanY = closes.reduce((total, close) => total + close, 0) / closes.length;
  const slope =
    closes.reduce((total, close, index) => total + (index - meanX) * (close - meanY), 0) /
    closes.reduce((total, _, index) => total + (index - meanX) ** 2, 0);
  const last = history.at(-1)!;

  return [
    { label: last.day, value: last.close },
    ...Array.from({ length: projectionWindow }, (_, index) => ({
      label: `T+${index + 1}`,
      value: last.close + slope * (index + 1),
    })),
  ];
}

export function moveDirection(changePercent: number) {
  const tolerance = 1e-10;
  return changePercent > flatMovePercent + tolerance
    ? "up"
    : changePercent < -flatMovePercent - tolerance
      ? "down"
      : "flat";
}

export type ProjectionResult = {
  origin: CompanyBar;
  target: CompanyBar;
  predicted: number;
  error: number;
  errorPercent: number;
  projectedMove: number;
  actualMove: number;
  matched: boolean;
};

export function projectionResults(
  candles: CompanyBar[],
  horizon: number,
  now = Date.now(),
): ProjectionResult[] {
  if (![1, 5, 20].includes(horizon)) return [];
  const results: ProjectionResult[] = [];
  for (let index = projectionWindow - 1; index + horizon < candles.length; index++) {
    const origin = candles[index];
    const target = candles[index + horizon];
    const interval = candles.slice(index, index + horizon + 1);
    if (
      interval.some(
        (bar, offset) =>
          !Number.isFinite(bar.close) ||
          bar.close <= 0 ||
          !Number.isFinite(sessionClose(bar.day)) ||
          sessionClose(bar.day) > now ||
          (offset > 0 && bar.day <= interval[offset - 1].day),
      )
    )
      continue;
    const projected = projectClosingPrices(
      candles.slice(Math.max(0, index + 1 - projectionWindow), index + 1),
    );
    if (!projected.length) continue;
    const predicted = projected[horizon].value;
    const error = target.close - predicted;
    const projectedMove = (predicted / origin.close - 1) * 100;
    const actualMove = (target.close / origin.close - 1) * 100;
    results.push({
      origin,
      target,
      predicted,
      error,
      errorPercent: (error / target.close) * 100,
      projectedMove,
      actualMove,
      matched: moveDirection(projectedMove) === moveDirection(actualMove),
    });
  }
  return results.slice(-60);
}

export function projectionSummary(results: ProjectionResult[]) {
  if (!results.length) return null;
  const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;
  return {
    count: results.length,
    mae: mean(results.map((result) => Math.abs(result.error))),
    rmse: Math.sqrt(mean(results.map((result) => result.error ** 2))),
    mape: mean(results.map((result) => Math.abs(result.errorPercent))),
    bias: mean(results.map((result) => result.error)),
    directionAccuracy: mean(results.map((result) => Number(result.matched))) * 100,
    baselineMae: mean(results.map((result) => Math.abs(result.target.close - result.origin.close))),
  };
}

export function newsInWindow(news: CompanyStory[], start: number, end: number) {
  return news
    .filter((story) => {
      if (!story.published_at) return false;
      const published = Date.parse(story.published_at);
      return published > start && published <= end;
    })
    .sort((a, b) => Date.parse(a.published_at!) - Date.parse(b.published_at!));
}

export type OutlookResult = {
  signal: CompanySignal;
  state: "Matched" | "Missed" | "Pending" | "Not verifiable";
  reason: string;
  actualClose: number | null;
  actualMove: number | null;
  start: number | null;
};

export function outlookResults(
  signals: CompanySignal[],
  candles: CompanyBar[],
  now = Date.now(),
): OutlookResult[] {
  const earliest = new Map<string, CompanySignal>();
  for (const signal of [...signals].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
  )) {
    if (!earliest.has(signal.target_date)) earliest.set(signal.target_date, signal);
  }
  return [...earliest.values()]
    .sort((a, b) => b.target_date.localeCompare(a.target_date))
    .map((signal) => {
      const { close, price_as_of: priceDay } = signal.inputs;
      const created = Date.parse(signal.created_at);
      const opening = Date.parse(`${signal.target_date}T09:15:00+05:30`);
      const start = typeof priceDay === "string" ? sessionClose(priceDay) : Number.NaN;
      const base: OutlookResult = {
        signal,
        state: "Not verifiable",
        reason: "",
        actualClose: null,
        actualMove: null,
        start: Number.isFinite(created) ? created : null,
      };
      if (
        typeof close !== "number" ||
        !Number.isFinite(close) ||
        close <= 0 ||
        typeof priceDay !== "string" ||
        priceDay >= signal.target_date ||
        !Number.isFinite(start) ||
        !Number.isFinite(created) ||
        !Number.isFinite(opening) ||
        created < start ||
        created >= opening ||
        !["up", "down", "flat"].includes(signal.direction)
      ) {
        return {
          ...base,
          reason:
            "Missing baseline evidence or not saved before the target session opened; excluded from accuracy.",
        };
      }
      if (sessionClose(signal.target_date) > now)
        return { ...base, state: "Pending", reason: "Target session has not completed." };
      const actual = candles.find((bar) => bar.day === signal.target_date);
      if (!actual || !Number.isFinite(actual.close) || actual.close <= 0)
        return {
          ...base,
          reason:
            "Completed target-session close is not in saved history; no substitute day is used.",
        };
      const actualMove = (actual.close / close - 1) * 100;
      const matched = moveDirection(actualMove) === signal.direction;
      return {
        ...base,
        state: matched ? "Matched" : "Missed",
        actualClose: actual.close,
        actualMove,
        reason: `Saved direction ${signal.direction}; realized ${moveDirection(actualMove)} using a +/-${flatMovePercent}% flat band. Score is not a predicted return or probability.`,
      };
    });
}
