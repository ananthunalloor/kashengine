/*
 * Placeholder data for the v2 Today (dashboard) mock page. Everything here is fictional.
 */
import { companies } from "./data";

export const todayMeta = {
  date: "2026-01-12",
  asOf: "11:42",
};

export const outlook = {
  index: "Sample Index 50",
  direction: "up" as const,
  strength: 7.2,
  newsScore: 6.8,
  newsArticles: 48,
  globalScore: 6.1,
  notes: "Positive overnight cues and broad-based positive news flow in sample IT and auto names.",
  stats: { correct: 62, total: 90, accuracy: 68.9, baseline: 54.4 },
  cues: [
    { instrument: "Sample US Tech Index", change: 1.42, date: "2026-01-09" },
    { instrument: "Sample Asia Index", change: 0.86, date: "2026-01-12" },
    { instrument: "Sample Crude Future", change: -1.12, date: "2026-01-09" },
    { instrument: "Sample Dollar Index", change: -0.31, date: "2026-01-09" },
    { instrument: "Sample Europe Index", change: 0.54, date: "2026-01-09" },
  ],
};

export const indexExtras: Record<
  string,
  { low: number; high: number; prevClose: number; lastTrade: string }
> = {
  IDX50: { low: 24180.4, high: 24352.1, prevClose: 24168.9, lastTrade: "11:41:58" },
  IDX30: { low: 79410.0, high: 79960.3, prevClose: 79356.45, lastTrade: "11:41:57" },
  BANKX: { low: 52080.15, high: 52410.8, prevClose: 52304.65, lastTrade: "11:41:58" },
  VOLX: { low: 12.71, high: 13.22, prevClose: 13.16, lastTrade: "11:41:50" },
};

export const breadth = { advancers: 1420, decliners: 780, unchanged: 92 };

export type NewsBias = "bullish" | "bearish" | "mixed" | "none";

export type WatchStock = {
  companyId: string;
  symbol: string;
  name: string;
  sector: string;
  price: number;
  changePct: number;
  bias: NewsBias;
  balance: number;
  articles: number;
  sources: number;
  latest: string;
  positive: number;
  negative: number;
  headlines: { title: string; source: string; time: string; reason: string }[];
};

const pick = (i: number) => companies[i];

export const stocksToWatch: WatchStock[] = [
  {
    companyId: pick(2).id,
    symbol: pick(2).symbol,
    name: pick(2).name,
    sector: pick(2).sector,
    price: pick(2).last,
    changePct: 1.4,
    bias: "bullish",
    balance: 0.64,
    articles: 12,
    sources: 4,
    latest: "8m ago",
    positive: 9,
    negative: 2,
    headlines: [
      {
        title: "Sample multi-year services contract announced in a new region",
        source: "Sample Wire",
        time: "11:34 IST",
        reason: "Adds visible revenue for the next several quarters.",
      },
      {
        title: "Brokerage raises sample target on deal momentum",
        source: "Example Times",
        time: "10:12 IST",
        reason: "Upgrade cites improving order pipeline.",
      },
    ],
  },
  {
    companyId: pick(0).id,
    symbol: pick(0).symbol,
    name: pick(0).name,
    sector: pick(0).sector,
    price: pick(0).last,
    changePct: 0.88,
    bias: "bullish",
    balance: 0.51,
    articles: 18,
    sources: 6,
    latest: "14m ago",
    positive: 12,
    negative: 4,
    headlines: [
      {
        title: "Acme Industries expands retail footprint with 120 sample stores",
        source: "Demo Business Daily",
        time: "11:28 IST",
        reason: "Store expansion supports volume growth.",
      },
    ],
  },
  {
    companyId: pick(1).id,
    symbol: pick(1).symbol,
    name: pick(1).name,
    sector: pick(1).sector,
    price: pick(1).last,
    changePct: -0.69,
    bias: "mixed",
    balance: -0.05,
    articles: 9,
    sources: 3,
    latest: "27m ago",
    positive: 4,
    negative: 4,
    headlines: [
      {
        title: "Bluefin Bank deposit growth stabilises; brokerage stays neutral",
        source: "Sample Wire",
        time: "11:15 IST",
        reason: "Positive deposit trend offset by margin pressure.",
      },
    ],
  },
  {
    companyId: pick(6).id,
    symbol: pick(6).symbol,
    name: pick(6).name,
    sector: pick(6).sector,
    price: pick(6).last,
    changePct: -1.84,
    bias: "bearish",
    balance: -0.58,
    articles: 1,
    sources: 1,
    latest: "46m ago",
    positive: 0,
    negative: 1,
    headlines: [
      {
        title: "Granite Metals flags higher sample input costs for the quarter",
        source: "Example Times",
        time: "10:56 IST",
        reason: "Cost pressure likely to squeeze margins.",
      },
    ],
  },
];

export type NewsItem = {
  id: string;
  score: number;
  symbol: string;
  title: string;
  source: string;
  time: string;
  reason: string;
};

export const newsHighlights: NewsItem[] = [
  {
    id: "nw1",
    score: 0.72,
    symbol: pick(10).symbol,
    title: "Kestrel Software guides for margin expansion on new enterprise deals",
    source: "Sample Wire",
    time: "18m ago",
    reason: "Operating efficiency offsets wage revisions.",
  },
  {
    id: "nw2",
    score: 0.65,
    symbol: pick(4).symbol,
    title: "Everest Motors order book crosses a sample record",
    source: "Example Times",
    time: "34m ago",
    reason: "Premium product mix lifts realisations.",
  },
  {
    id: "nw3",
    score: -0.58,
    symbol: pick(9).symbol,
    title: "Juniper Finance sees higher slippages in unsecured loans",
    source: "Demo Business Daily",
    time: "46m ago",
    reason: "Credit costs expected to rise next quarters.",
  },
  {
    id: "nw4",
    score: 0.44,
    symbol: pick(12).symbol,
    title: "Meridian Auto Parts festive dispatches up 14% year on year",
    source: "Sample Wire",
    time: "1h ago",
    reason: "Channel inventory clearing quickly.",
  },
  {
    id: "nw5",
    score: -0.31,
    symbol: pick(17).symbol,
    title: "Redwood Capital faces sample regulatory review",
    source: "Example Times",
    time: "1h ago",
    reason: "Uncertainty around new business approvals.",
  },
  {
    id: "nw6",
    score: 0.38,
    symbol: pick(5).symbol,
    title: "Fernhill Pharma clears sample plant inspection with no observations",
    source: "Demo Business Daily",
    time: "1h 20m ago",
    reason: "De-risks export pipeline.",
  },
];

export type IpoCard = {
  id: string;
  name: string;
  band: [number, number];
  dates: string;
  verdict: "Likely positive" | "Neutral" | "Avoid";
  score: number;
  premiumPct: number;
};

export const ipoGroups: Record<"likely" | "open" | "soon", IpoCard[]> = {
  likely: [
    {
      id: "sample-ipo",
      name: "Sample Solar Ltd",
      band: [1427, 1503],
      dates: "Closes 14 Jan",
      verdict: "Likely positive",
      score: 7.8,
      premiumPct: 18.4,
    },
    {
      id: "sample-ipo-2",
      name: "Example Logistics Ltd",
      band: [210, 222],
      dates: "Opens 15 Jan",
      verdict: "Likely positive",
      score: 6.9,
      premiumPct: 9.1,
    },
  ],
  open: [
    {
      id: "sample-ipo",
      name: "Sample Solar Ltd",
      band: [1427, 1503],
      dates: "Closes 14 Jan",
      verdict: "Likely positive",
      score: 7.8,
      premiumPct: 18.4,
    },
    {
      id: "sample-ipo-3",
      name: "Demo Infra Projects",
      band: [440, 463],
      dates: "Closes 13 Jan",
      verdict: "Neutral",
      score: 4.6,
      premiumPct: 2.6,
    },
  ],
  soon: [
    {
      id: "sample-ipo-2",
      name: "Example Logistics Ltd",
      band: [210, 222],
      dates: "Opens 15 Jan",
      verdict: "Likely positive",
      score: 6.9,
      premiumPct: 9.1,
    },
    {
      id: "sample-ipo-4",
      name: "Placeholder Fintech",
      band: [95, 100],
      dates: "Opens 19 Jan",
      verdict: "Avoid",
      score: 2.8,
      premiumPct: -1.5,
    },
  ],
};

export const topMovers = {
  gainers: [...companies].sort((a, b) => b.changePct - a.changePct).slice(0, 4),
  losers: [...companies].sort((a, b) => a.changePct - b.changePct).slice(0, 4),
};

export const latestReport = {
  date: "2026-01-12",
  title: "Positive cues and steady flows support the sample benchmark",
  lines: [
    "Sample equities start the week with supportive overseas cues and steady domestic flows.",
    "IT services and autos lead the positive news flow; banks are mixed after deposit updates.",
    "Watch the sample volatility index, which eased 2.4% and sits near a three-month low.",
  ],
  readMinutes: 3,
};

export const deliveryStatus = [
  { channel: "Email", target: "user@example.com", state: "sent" as const, time: "08:05 IST" },
  { channel: "Telegram", target: "@sample_channel", state: "sent" as const, time: "08:05 IST" },
  { channel: "Webhook", target: "example.com/hook", state: "failed" as const, time: "08:06 IST" },
];
