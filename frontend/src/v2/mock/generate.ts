/** Deterministic pseudo-random generator so mock pages render identically on every load. */
export function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

export type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export function mockCandles(count = 90, start = 1000, seed = 7): Candle[] {
  const rand = seeded(seed);
  const out: Candle[] = [];
  let close = start;
  const day = new Date(Date.UTC(2025, 0, 1));
  for (let i = 0; i < count; i++) {
    while (day.getUTCDay() === 0 || day.getUTCDay() === 6) day.setUTCDate(day.getUTCDate() + 1);
    const open = close * (1 + (rand() - 0.5) * 0.01);
    close = open * (1 + (rand() - 0.48) * 0.03);
    const high = Math.max(open, close) * (1 + rand() * 0.01);
    const low = Math.min(open, close) * (1 - rand() * 0.01);
    out.push({
      date: day.toISOString().slice(0, 10),
      open,
      high,
      low,
      close,
      volume: Math.round(2e5 + rand() * 8e5),
    });
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return out;
}

export function mockSeries(count = 30, start = 100, seed = 3, drift = 0.002): number[] {
  const rand = seeded(seed);
  const out: number[] = [];
  let v = start;
  for (let i = 0; i < count; i++) {
    v *= 1 + (rand() - 0.5 + drift) * 0.02;
    out.push(Number(v.toFixed(2)));
  }
  return out;
}

export function sma(values: number[], period: number): Array<number | null> {
  return values.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    return sum / period;
  });
}
