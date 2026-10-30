/*
 * Placeholder Markets data for the v2 mock pages: prediction track record, saved quotes and an
 * instrument master. Every name, symbol, ISIN and number is fictional sample data.
 */
import { companies } from "./data";
import { seeded } from "./generate";

export type Direction = "up" | "down" | "flat";
export type PredictionResult = "right" | "wrong" | "no-session" | "waiting";

export type Prediction = {
  date: string;
  said: Direction | "withheld";
  strength: number;
  actual: Direction | null;
  changePct: number | null;
  result: PredictionResult;
  cue: string;
};

const cues = [
  "Positive global cues overnight",
  "Banking results beat estimates",
  "Weak sample currency",
  "Crude price fell 2%",
  "Foreign selling in futures",
  "Strong delivery in large caps",
  "Rate-decision uncertainty",
  "IT guidance cut by a sample firm",
];

function tradingDays(endIso: string, count: number): string[] {
  const out: string[] = [];
  const d = new Date(`${endIso}T00:00:00Z`);
  while (out.length < count) {
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() - 1);
  }
  return out;
}

const pattern = "RRRWRRRWRRRRWRRRRWRRRWRRWRRRRN";

function buildPredictions(): Prediction[] {
  const rand = seeded(910);
  const days = tradingDays("2026-10-29", 30);
  return days.map((date, i) => {
    const cue = cues[i % cues.length];
    if (i === 0) {
      return {
        date,
        said: "up",
        strength: 7.2,
        actual: null,
        changePct: null,
        result: "waiting",
        cue,
      };
    }
    if (date === "2026-10-20") {
      return {
        date,
        said: "withheld",
        strength: 0,
        actual: null,
        changePct: null,
        result: "no-session",
        cue: "Sample holiday H",
      };
    }
    const right = pattern[i] !== "W";
    const said: Direction = rand() > 0.42 ? "up" : rand() > 0.15 ? "down" : "flat";
    const actual: Direction = right ? said : said === "up" ? "down" : "up";
    const magnitude = 0.1 + rand() * 1.2;
    const changePct =
      actual === "flat"
        ? Number((rand() * 0.1 - 0.05).toFixed(2))
        : Number((actual === "up" ? magnitude : -magnitude).toFixed(2));
    return {
      date,
      said,
      strength: Number((3 + rand() * 6.5).toFixed(1)),
      actual,
      changePct,
      result: right ? "right" : "wrong",
      cue,
    };
  });
}

export const predictions: Prediction[] = buildPredictions();

export const trackRecord = {
  correct: 84,
  total: 110,
  baseline: 51.2,
  strongCorrect: 46,
  strongTotal: 56,
  streak: 5,
  lastMiss: "2026-10-22",
  pending: 1,
  nextSettlement: "29 Oct 2026, 15:30 IST",
};

export type Quote = {
  id: string;
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  freshness: "live" | "delayed" | "stale" | "closed";
  fetchedAt: string | null;
  error: string | null;
};

export const quotes: Quote[] = companies.map((c, i) => {
  const freshness: Quote["freshness"] = i % 9 === 4 ? "stale" : i % 5 === 2 ? "delayed" : "live";
  return {
    id: c.id,
    symbol: c.symbol,
    name: c.name,
    price: c.last,
    changePct: c.changePct,
    freshness: i === 17 ? "closed" : freshness,
    fetchedAt:
      i === 21
        ? null
        : freshness === "stale"
          ? "10:58 IST"
          : freshness === "delayed"
            ? "11:39 IST"
            : "11:42 IST",
    error: freshness === "stale" ? "Sample provider timeout (HTTP 504)" : null,
  };
});

export type Instrument = {
  key: string;
  symbol: string;
  name: string;
  companyId: string | null;
  exchange: "NSE" | "BSE";
  segment: "Equity" | "F&O" | "Index";
  type: "EQ" | "FUT" | "CE" | "PE" | "INDEX";
  isin: string | null;
  underlying: string | null;
  expiry: string | null;
  strike: number | null;
  lotSize: number;
};

function buildInstruments(): Instrument[] {
  const out: Instrument[] = [];
  companies.forEach((c, i) => {
    const isin = `INE0SMP${String(i + 1).padStart(4, "0")}9`;
    for (const exchange of ["NSE", "BSE"] as const) {
      out.push({
        key: `${exchange}-${c.symbol}-EQ`,
        symbol: c.symbol,
        name: c.name,
        companyId: c.id,
        exchange,
        segment: "Equity",
        type: "EQ",
        isin,
        underlying: null,
        expiry: null,
        strike: null,
        lotSize: 1,
      });
    }
    if (i < 8) {
      const lot = 250 * ((i % 4) + 1);
      out.push({
        key: `NSE-${c.symbol}-FUT`,
        symbol: `${c.symbol}26NOVFUT`,
        name: `${c.name} Nov futures`,
        companyId: c.id,
        exchange: "NSE",
        segment: "F&O",
        type: "FUT",
        isin: null,
        underlying: c.symbol,
        expiry: "2026-11-26",
        strike: null,
        lotSize: lot,
      });
      const strike = Math.round(c.last / 50) * 50;
      for (const type of ["CE", "PE"] as const) {
        out.push({
          key: `NSE-${c.symbol}-${strike}${type}`,
          symbol: `${c.symbol}26NOV${strike}${type}`,
          name: `${c.name} ${strike} ${type === "CE" ? "call" : "put"}`,
          companyId: c.id,
          exchange: "NSE",
          segment: "F&O",
          type,
          isin: null,
          underlying: c.symbol,
          expiry: "2026-11-26",
          strike,
          lotSize: lot,
        });
      }
    }
  });
  for (const idx of ["IDX50", "IDX30", "BANKX", "VOLX"]) {
    out.push({
      key: `NSE-${idx}-INDEX`,
      symbol: idx,
      name: `Sample index ${idx}`,
      companyId: null,
      exchange: idx === "IDX30" ? "BSE" : "NSE",
      segment: "Index",
      type: "INDEX",
      isin: null,
      underlying: null,
      expiry: null,
      strike: null,
      lotSize: 1,
    });
  }
  return out;
}

export const instruments: Instrument[] = buildInstruments();

export const instrumentsImportedAt = "29 Oct 2026, 07:30 IST";
