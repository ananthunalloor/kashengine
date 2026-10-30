/*
 * Placeholder scored news for the v2 News page. Headlines, sources, scores and companies are
 * fictional sample data used only to exercise layouts.
 */
import { companies } from "./data";
import { seeded } from "./generate";

export type Region = "local" | "international";

export type ScoreFactor = { phrase: string; effect: number };

export type Article = {
  id: string;
  title: string;
  /** One-line AI explanation of the score. */
  reason: string;
  topic: string;
  source: string;
  region: Region;
  /** Minutes before the mock "now" (14:30 IST). */
  minutesAgo: number;
  /** −1..+1, null when the article has not been scored yet. */
  sentiment: number | null;
  /** 0..1, how much the story matters for the linked companies. */
  relevance: number;
  confidence: number;
  companyIds: string[];
  factors: ScoreFactor[];
  url: string;
};

export const NEWS_NOW = { day: "2026-10-29", minutes: 14 * 60 + 30 };

export const newsSources = [
  "Sample Wire",
  "Example Business Daily",
  "Exchange filing (sample)",
  "Demo Markets Desk",
  "Global Ledger (sample)",
  "World Example Times",
];

const internationalSources = new Set(["Global Ledger (sample)", "World Example Times"]);

type Template = {
  title: string;
  reason: string;
  topic: string;
  base: number;
  factors: ScoreFactor[];
  global?: boolean;
};

const templates: Template[] = [
  {
    title: "{c} wins sample export order worth ₹{n} Cr",
    reason: "Large order relative to annual revenue lifts earnings visibility.",
    topic: "Order win",
    base: 0.74,
    factors: [
      { phrase: "order worth ₹{n} Cr", effect: 0.42 },
      { phrase: "multi-year contract", effect: 0.21 },
      { phrase: "execution risk noted", effect: -0.08 },
    ],
  },
  {
    title: "{c} quarterly profit rises on steady sample demand",
    reason: "Profit beat with stable margins; tone is positive but expected.",
    topic: "Results",
    base: 0.48,
    factors: [
      { phrase: "profit rises", effect: 0.31 },
      { phrase: "margins stable", effect: 0.12 },
      { phrase: "in line with estimates", effect: -0.04 },
    ],
  },
  {
    title: "{c} flags higher input costs for the next quarter",
    reason: "Margin guidance cut; management commentary is cautious.",
    topic: "Guidance",
    base: -0.52,
    factors: [
      { phrase: "higher input costs", effect: -0.34 },
      { phrase: "guidance trimmed", effect: -0.22 },
      { phrase: "volume outlook intact", effect: 0.06 },
    ],
  },
  {
    title: "Sample regulator seeks clarification from {c} on disclosure",
    reason: "Governance query adds uncertainty until the company responds.",
    topic: "Regulatory",
    base: -0.61,
    factors: [
      { phrase: "seeks clarification", effect: -0.29 },
      { phrase: "disclosure lapse", effect: -0.3 },
    ],
  },
  {
    title: "{c} board approves capacity expansion in sample region",
    reason: "Capex signals demand confidence; funding details still pending.",
    topic: "Capex",
    base: 0.36,
    factors: [
      { phrase: "capacity expansion", effect: 0.28 },
      { phrase: "funding not disclosed", effect: -0.06 },
    ],
  },
  {
    title: "{c} monthly volumes flat year on year",
    reason: "No surprise versus sample estimates; limited price impact.",
    topic: "Monthly data",
    base: 0.02,
    factors: [
      { phrase: "volumes flat", effect: -0.03 },
      { phrase: "inventory normal", effect: 0.04 },
    ],
  },
  {
    title: "Sample central bank holds policy rate, keeps liquidity stance",
    reason: "Expected outcome; mildly dovish commentary helps rate-sensitive lenders.",
    topic: "Macro",
    base: 0.22,
    factors: [
      { phrase: "rate unchanged", effect: 0.05 },
      { phrase: "ample liquidity", effect: 0.17 },
    ],
  },
  {
    title: "Crude climbs on sample supply concerns; refiners under pressure",
    reason: "Higher input costs for fuel retailers and chemical makers.",
    topic: "Commodities",
    base: -0.55,
    global: true,
    factors: [
      { phrase: "crude climbs", effect: -0.32 },
      { phrase: "supply concerns", effect: -0.18 },
    ],
  },
  {
    title: "Overseas tech spending survey points to recovery in sample market",
    reason: "Better client budgets support export-oriented IT names.",
    topic: "Global",
    base: 0.41,
    global: true,
    factors: [
      { phrase: "spending recovery", effect: 0.3 },
      { phrase: "survey-based, early signal", effect: -0.05 },
    ],
  },
  {
    title: "{c} promoter pledges additional shares (sample filing)",
    reason: "Rising pledge is read as a funding-stress signal.",
    topic: "Shareholding",
    base: -0.44,
    factors: [
      { phrase: "pledges additional shares", effect: -0.36 },
      { phrase: "small stake", effect: 0.05 },
    ],
  },
];

function buildArticles(count: number): Article[] {
  const rand = seeded(20261029);
  const out: Article[] = [];
  let minutes = 3;
  for (let i = 0; i < count; i++) {
    const t = templates[Math.floor(rand() * templates.length)];
    const first = companies[Math.floor(rand() * companies.length)];
    const extra =
      rand() < 0.35 ? [companies[(companies.indexOf(first) + 5) % companies.length]] : [];
    const n = String(150 + Math.floor(rand() * 9000));
    const source = t.global
      ? [...internationalSources][Math.floor(rand() * internationalSources.size)]
      : newsSources[Math.floor(rand() * 4)];
    const unscored = i > 2 && rand() < 0.08;
    const sentiment = unscored
      ? null
      : Number(Math.max(-1, Math.min(1, t.base + (rand() - 0.5) * 0.25)).toFixed(2));
    const sector = companies
      .filter((c) => c.sector === first.sector && c.id !== first.id)
      .slice(0, 2);
    out.push({
      id: `n${i + 1}`,
      title: t.title.replace("{c}", first.name).replace("{n}", n),
      reason: t.reason,
      topic: t.topic,
      source,
      region: internationalSources.has(source) ? "international" : "local",
      minutesAgo: minutes,
      sentiment,
      relevance: Number((0.45 + rand() * 0.55).toFixed(2)),
      confidence: Number((0.6 + rand() * 0.38).toFixed(2)),
      companyIds:
        t.global || t.topic === "Macro"
          ? sector.map((c) => c.id)
          : [first.id, ...extra.map((c) => c.id)],
      factors: t.factors.map((f) => ({ ...f, phrase: f.phrase.replace("{n}", n) })),
      url: `https://example.com/sample-news/${i + 1}`,
    });
    minutes += 4 + Math.floor(rand() * 55);
  }
  return out;
}

/** Newest first. */
export const articles: Article[] = buildArticles(64);

/** Hourly sentiment mix for the last 8 hours (sample). */
export const sentimentByHour = Array.from({ length: 8 }, (_, i) => {
  const hourEnd = NEWS_NOW.minutes - i * 60;
  const inHour = articles.filter((a) => {
    const at = NEWS_NOW.minutes - a.minutesAgo;
    return at <= hourEnd && at > hourEnd - 60 && a.sentiment != null;
  });
  const hour = Math.floor((hourEnd - 1) / 60);
  return {
    hour: `${String(hour).padStart(2, "0")}:00`,
    Positive: inHour.filter((a) => (a.sentiment ?? 0) >= 0.15).length,
    Neutral: inHour.filter((a) => Math.abs(a.sentiment ?? 0) < 0.15).length,
    Negative: inHour.filter((a) => (a.sentiment ?? 0) <= -0.15).length,
  };
}).reverse();
