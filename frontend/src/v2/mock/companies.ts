/*
 * Placeholder detail data for the v2 Companies pages. Everything is fictional and derived
 * deterministically from the shared `companies` list so pages render the same on every load.
 */
import type { Company } from "./data";
import { companies } from "./data";
import { seeded } from "./generate";

export const sectorOptions = Array.from(new Set(companies.map((c) => c.sector))).sort();

export const indexOptions = [
  { value: "all", label: "All companies", count: companies.length },
  { value: "idx50", label: "Sample Index 50", count: 16 },
  { value: "next", label: "Sample Next 50", count: 8 },
];

/** Which sample index a company belongs to (fictional membership). */
export function indexOf(company: Company): "idx50" | "next" {
  return companies.indexOf(company) < 16 ? "idx50" : "next";
}

export function findCompany(id: string): Company {
  return companies.find((c) => c.id === id) ?? companies[0];
}

export function companySeed(company: Company): number {
  return 500 + companies.indexOf(company) * 17;
}

export type QuarterRow = {
  quarter: string;
  revenue: number;
  ebitda: number;
  profit: number;
  margin: number;
};
export type YearRow = {
  year: string;
  revenue: number;
  profit: number;
  eps: number;
  roe: number;
  debtEquity: number;
};
export type Multiple = { name: string; company: number; sector: number; info: string };
export type CompanyNews = {
  id: string;
  title: string;
  source: string;
  date: string;
  time: string;
  score: number;
  relevance: number;
  reason: string;
};
export type DeliveryDay = {
  date: string;
  volume: number;
  delivered: number;
  deliveryPct: number;
  close: number;
};
export type MarketDepthLevel = {
  bidPrice: number;
  bidQty: number;
  askPrice: number;
  askQty: number;
};
export type IpoScoreInput = {
  name: string;
  value: string;
  score: number;
  note: string;
};

export type CompanyDetail = {
  about: string;
  founded: number;
  hq: string;
  employees: number;
  isin: string;
  bseCode: string;
  dataFrom: string;
  prevClose: number;
  open: number;
  high: number;
  low: number;
  week52High: number;
  week52Low: number;
  beta: number;
  dividendYield: number;
  pb: number;
  bookValue: number;
  averagePrice: number;
  totalBuyQty: number;
  totalSellQty: number;
  marketDepth: MarketDepthLevel[];
  ipoScores: Array<{
    id: string;
    name: string;
    verdict: "positive" | "neutral" | "avoid";
    score: number;
    scoredAt: string;
    inputs: IpoScoreInput[];
  }>;
  outlook: { direction: "up" | "down" | "flat"; score: number; target: number };
  momentum: number;
  sentiment: { score: number; positive: number; neutral: number; negative: number };
  valuation: "In line" | "Sector premium" | "Sector discount";
  quarters: QuarterRow[];
  years: YearRow[];
  multiples: Multiple[];
  shareholding: Array<{ name: string; value: number; color: string }>;
  news: CompanyNews[];
  delivery: DeliveryDay[];
};

const sources = [
  "Sample Wire",
  "Example Business Daily",
  "Placeholder Markets",
  "Demo Financial Times",
];
const headlines: Array<[string, number, string]> = [
  [
    "{name} reports steady quarterly revenue growth",
    0.52,
    "Revenue beat the sample consensus estimate.",
  ],
  [
    "{name} board approves sample capacity expansion",
    0.41,
    "Capex signals medium-term volume growth.",
  ],
  ["Brokerage keeps neutral view on {name} after results", 0.04, "No change in rating or target."],
  [
    "{name} faces input cost pressure, margins narrow",
    -0.38,
    "Raw material prices rose in the quarter.",
  ],
  [
    "{name} signs supply agreement with fictional partner",
    0.33,
    "New contract adds to order book.",
  ],
  [
    "Regulator seeks clarification from {name} on disclosure",
    -0.46,
    "Compliance query; outcome pending.",
  ],
  ["{name} declares interim dividend for sample year", 0.22, "Payout in line with past policy."],
  ["Sector peers outperform {name} in monthly volumes", -0.18, "Market share slipped slightly."],
];

function shareholding(rand: () => number) {
  const promoters = 45 + Math.round(rand() * 15);
  const foreign = 15 + Math.round(rand() * 8);
  const domestic = 10 + Math.round(rand() * 8);
  return [
    { name: "Promoters", value: promoters, color: "indigo.6" },
    { name: "Foreign inst.", value: foreign, color: "sky.6" },
    { name: "Domestic inst.", value: domestic, color: "emerald.6" },
    { name: "Public", value: 100 - promoters - foreign - domestic, color: "slate.4" },
  ];
}

export function companyDetail(company: Company): CompanyDetail {
  const rand = seeded(companySeed(company));
  const last = company.last;
  const prevClose = last / (1 + company.changePct / 100);
  const revenueBase = company.marketCap / (company.pe * 1.8);
  const quarters: QuarterRow[] = ["Q3 FY25", "Q4 FY25", "Q1 FY26", "Q2 FY26", "Q3 FY26"].map(
    (quarter, i) => {
      const revenue = (revenueBase / 4) * (0.9 + i * 0.035 + rand() * 0.05);
      const margin = 0.12 + rand() * 0.1;
      const ebitda = revenue * (margin + 0.06);
      return { quarter, revenue, ebitda, profit: revenue * margin, margin: margin * 100 };
    },
  );
  const years: YearRow[] = ["FY22", "FY23", "FY24", "FY25"].map((year, i) => {
    const revenue = revenueBase * (0.72 + i * 0.09 + rand() * 0.04);
    const profit = revenue * (0.1 + rand() * 0.08);
    return {
      year,
      revenue,
      profit,
      eps: (profit / company.marketCap) * last * company.pe * 0.06 + 5,
      roe: 11 + rand() * 12,
      debtEquity: 0.1 + rand() * 0.9,
    };
  });
  const pb = 1.5 + rand() * 5;
  const sectorPe = company.pe * (0.85 + rand() * 0.3);
  const ratio = company.pe / sectorPe;
  const positive = 6 + Math.floor(rand() * 10);
  const neutral = 2 + Math.floor(rand() * 5);
  const negative = Math.floor(rand() * 5);
  const sentimentScore = Number(
    ((positive - negative) / (positive + neutral + negative)).toFixed(2),
  );
  const ipoRand = seeded(companySeed(company) + 9);
  const marketRand = seeded(companySeed(company) + 7);
  const ipoScore = Number(((ipoRand() - 0.5) * 1.5).toFixed(2));
  const outlookScore = Number((4 + rand() * 5).toFixed(1));
  const direction =
    company.signal === "Accumulation" ? "up" : company.signal === "Distribution" ? "down" : "flat";

  const deliveryRand = seeded(companySeed(company) + 3);
  const depthRand = seeded(companySeed(company) + 5);
  const spread = last * 0.0005;
  const marketDepth: MarketDepthLevel[] = Array.from({ length: 5 }, (_, i) => ({
    bidPrice: Number((last - spread * (i + 1)).toFixed(2)),
    bidQty: Math.round(100 + depthRand() * 900),
    askPrice: Number((last + spread * (i + 1)).toFixed(2)),
    askQty: Math.round(100 + depthRand() * 900),
  }));
  const delivery: DeliveryDay[] = [];
  let close = prevClose * 0.97;
  const day = new Date(Date.UTC(2026, 0, 12));
  while (delivery.length < 20) {
    if (day.getUTCDay() !== 0 && day.getUTCDay() !== 6) {
      const volume = Math.round(company.volume * (0.6 + deliveryRand() * 0.9));
      const pct = Math.max(15, Math.min(90, company.deliveryPct + (deliveryRand() - 0.5) * 24));
      delivery.unshift({
        date: day.toISOString().slice(0, 10),
        volume,
        delivered: Math.round((volume * pct) / 100),
        deliveryPct: Number(pct.toFixed(1)),
        close,
      });
      close *= 1 + (deliveryRand() - 0.5) * 0.02;
    }
    day.setUTCDate(day.getUTCDate() - 1);
  }

  return {
    about: `${company.name} is a fictional ${company.sector.toLowerCase()} company used to demonstrate this page. It runs three sample business lines, sells mainly in the domestic market and exports to a handful of placeholder regions. None of these facts describe a real business.`,
    founded: 1970 + Math.floor(rand() * 45),
    hq: ["Sample City", "Example Town", "Placeholder Nagar", "Demo Bay"][Math.floor(rand() * 4)],
    employees: Math.round(1500 + rand() * 40000),
    isin: `INE0SAMPLE${String(companies.indexOf(company)).padStart(2, "0")}`,
    bseCode: String(900100 + companies.indexOf(company) * 7),
    dataFrom: "2026-01-12",
    prevClose,
    open: prevClose * (1 + (rand() - 0.5) * 0.008),
    high: Math.max(last, prevClose) * (1 + rand() * 0.01),
    low: Math.min(last, prevClose) * (1 - rand() * 0.01),
    week52High: last * (1.08 + rand() * 0.2),
    week52Low: last * (0.62 + rand() * 0.2),
    beta: Number((0.6 + rand() * 0.8).toFixed(2)),
    dividendYield: Number((rand() * 2.5).toFixed(2)),
    pb,
    bookValue: last / pb,
    averagePrice: Number((last * (0.997 + marketRand() * 0.006)).toFixed(2)),
    totalBuyQty: Math.round(company.volume * (0.12 + marketRand() * 0.08)),
    totalSellQty: Math.round(company.volume * (0.12 + marketRand() * 0.08)),
    marketDepth,
    ipoScores: [
      {
        id: `${company.id}-sample-issue`,
        name: `${company.name} · sample IPO score`,
        verdict: ipoScore > 0.25 ? "positive" : ipoScore < -0.25 ? "avoid" : "neutral",
        score: ipoScore,
        scoredAt: "2026-01-12 08:15 IST",
        inputs: [
          {
            name: "Subscription demand",
            value: `${formatSample(2 + ipoRand() * 4)}×`,
            score: Number((ipoRand() * 2 - 1).toFixed(2)),
            note: "Illustrative sample subscription signal.",
          },
          {
            name: "GMP (unofficial)",
            value: `${formatSample(ipoRand() * 14)}%`,
            score: Number((ipoRand() * 2 - 1).toFixed(2)),
            note: "Grey market premium is unofficial and indicative only.",
          },
          {
            name: "Financial trend",
            value: ipoRand() > 0.4 ? "Improving" : "Mixed",
            score: Number((ipoRand() * 2 - 1).toFixed(2)),
            note: "Derived from fictional revenue and profit history.",
          },
          {
            name: "Valuation vs peers",
            value: ipoRand() > 0.5 ? "In line" : "Premium",
            score: Number((ipoRand() * 2 - 1).toFixed(2)),
            note: "Illustrative peer comparison; not a fair-value estimate.",
          },
          {
            name: "Lead manager record",
            value: ipoRand() > 0.35 ? "Average" : "Limited data",
            score: Number((ipoRand() * 2 - 1).toFixed(2)),
            note: "Sample input; no real manager history is represented.",
          },
        ],
      },
    ],
    outlook: {
      direction,
      score: outlookScore,
      target: last * (1 + (direction === "up" ? 0.01 : direction === "down" ? -0.01 : 0.001)),
    },
    momentum: Number((3 + rand() * 6).toFixed(1)),
    sentiment: { score: sentimentScore, positive, neutral, negative },
    valuation: ratio > 1.1 ? "Sector premium" : ratio < 0.9 ? "Sector discount" : "In line",
    quarters,
    years,
    multiples: [
      {
        name: "P/E",
        company: company.pe,
        sector: sectorPe,
        info: "Price ÷ earnings per share (trailing 12 months).",
      },
      {
        name: "P/B",
        company: pb,
        sector: pb * (0.8 + rand() * 0.4),
        info: "Price ÷ book value per share.",
      },
      {
        name: "EV/EBITDA",
        company: company.pe * 0.6,
        sector: company.pe * (0.5 + rand() * 0.2),
        info: "Enterprise value ÷ operating profit before depreciation.",
      },
    ],
    shareholding: shareholding(rand),
    news: headlines.map(([title, score, reason], i) => ({
      id: `${company.id}-n${i}`,
      title: title.replace("{name}", company.name),
      source: sources[i % sources.length],
      date: `2026-01-${String(12 - Math.floor(i / 2)).padStart(2, "0")}`,
      time: `${String(8 + ((i * 3) % 9)).padStart(2, "0")}:${String((i * 17) % 60).padStart(2, "0")}`,
      score,
      relevance: Number((0.55 + ((i * 7) % 5) / 11).toFixed(2)),
      reason,
    })),
    delivery,
  };
}

function formatSample(value: number): string {
  return value.toFixed(1);
}
