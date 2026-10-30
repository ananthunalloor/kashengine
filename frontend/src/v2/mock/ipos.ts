/*
 * Placeholder IPO data for the v2 mock pages. Every company, symbol, manager and number here is
 * fictional sample data. Replace with API queries during the migration.
 */
import { seeded } from "./generate";

export type IpoStatus = "open" | "upcoming" | "listed" | "closed";
export type IpoBoard = "Mainboard" | "SME";
export type IpoVerdict = "positive" | "neutral" | "avoid";

export type IpoSignal = { name: string; value: string; score: number; note: string };
export type IpoFinancial = { year: string; revenue: number; profit: number; netWorth: number };

export type Ipo = {
  id: string;
  name: string;
  symbol: string;
  board: IpoBoard;
  status: IpoStatus;
  sector: string;
  openDate: string;
  closeDate: string;
  allotmentDate: string;
  listingDate: string;
  priceLow: number;
  priceHigh: number;
  lotSize: number;
  issueSize: number;
  freshPct: number;
  /** Overall subscription in times (x); null before bidding opens. */
  subscription: number | null;
  subByCategory: { category: string; times: number }[];
  /** Grey market premium in ₹ per share (unofficial). */
  gmp: number | null;
  /** Actual listing price, only for listed issues. */
  listedAt: number | null;
  verdict: IpoVerdict;
  score: number;
  managers: string;
  registrar: string;
  gmpTrend: { date: string; gmp: number }[];
  financials: IpoFinancial[];
  strengths: string[];
  risks: string[];
  signals: IpoSignal[];
  scoredAt: string;
};

type Seed = {
  name: string;
  board: IpoBoard;
  status: IpoStatus;
  sector: string;
  open: string;
  priceHigh: number;
  issueCr: number;
  sub: number | null;
  gmpPct: number | null;
  listedPct?: number;
  score: number;
};

const seeds: Seed[] = [
  {
    name: "Acme Logistics",
    board: "Mainboard",
    status: "open",
    sector: "Logistics",
    open: "2026-10-28",
    priceHigh: 463,
    issueCr: 5430,
    sub: 3.42,
    gmpPct: 15.5,
    score: 0.62,
  },
  {
    name: "Brightwave Retail",
    board: "Mainboard",
    status: "open",
    sector: "Consumer tech",
    open: "2026-10-29",
    priceHigh: 390,
    issueCr: 11327,
    sub: 0.84,
    gmpPct: 3.1,
    score: 0.18,
  },
  {
    name: "Copperleaf Foods",
    board: "SME",
    status: "open",
    sector: "FMCG",
    open: "2026-10-29",
    priceHigh: 96,
    issueCr: 42,
    sub: 12.6,
    gmpPct: 28.4,
    score: 0.44,
  },
  {
    name: "Duskline Energy",
    board: "Mainboard",
    status: "upcoming",
    sector: "Renewables",
    open: "2026-11-04",
    priceHigh: 215,
    issueCr: 2800,
    sub: null,
    gmpPct: 9.3,
    score: 0.35,
  },
  {
    name: "Elmstone Finance",
    board: "Mainboard",
    status: "upcoming",
    sector: "NBFC",
    open: "2026-11-06",
    priceHigh: 540,
    issueCr: 4100,
    sub: null,
    gmpPct: 1.2,
    score: -0.08,
  },
  {
    name: "Foxglove Pharma",
    board: "Mainboard",
    status: "upcoming",
    sector: "Pharma",
    open: "2026-11-10",
    priceHigh: 712,
    issueCr: 1650,
    sub: null,
    gmpPct: null,
    score: 0.05,
  },
  {
    name: "Granmoor Tools",
    board: "SME",
    status: "upcoming",
    sector: "Engineering",
    open: "2026-11-05",
    priceHigh: 72,
    issueCr: 28,
    sub: null,
    gmpPct: -4.0,
    score: -0.41,
  },
  {
    name: "Hollyridge Hotels",
    board: "SME",
    status: "upcoming",
    sector: "Hospitality",
    open: "2026-11-12",
    priceHigh: 118,
    issueCr: 36,
    sub: null,
    gmpPct: null,
    score: 0.0,
  },
  {
    name: "Ironbark Cables",
    board: "Mainboard",
    status: "closed",
    sector: "Electricals",
    open: "2026-10-22",
    priceHigh: 288,
    issueCr: 1240,
    sub: 48.2,
    gmpPct: 34.0,
    score: 0.71,
  },
  {
    name: "Jadeport Shipping",
    board: "SME",
    status: "closed",
    sector: "Logistics",
    open: "2026-10-21",
    priceHigh: 54,
    issueCr: 18,
    sub: 2.1,
    gmpPct: -2.5,
    score: -0.22,
  },
  {
    name: "Kingfern Insurance",
    board: "Mainboard",
    status: "listed",
    sector: "Insurance",
    open: "2026-10-08",
    priceHigh: 330,
    issueCr: 6500,
    sub: 1.6,
    gmpPct: 2.0,
    listedPct: -6.4,
    score: -0.3,
  },
  {
    name: "Larkspur Software",
    board: "Mainboard",
    status: "listed",
    sector: "IT services",
    open: "2026-10-01",
    priceHigh: 610,
    issueCr: 2100,
    sub: 92.4,
    gmpPct: 48.0,
    listedPct: 54.2,
    score: 0.81,
  },
  {
    name: "Mossgate Realty",
    board: "Mainboard",
    status: "listed",
    sector: "Real estate",
    open: "2026-09-24",
    priceHigh: 255,
    issueCr: 3000,
    sub: 4.3,
    gmpPct: 8.0,
    listedPct: 11.6,
    score: 0.24,
  },
  {
    name: "Nettlefield Agro",
    board: "SME",
    status: "listed",
    sector: "Agri inputs",
    open: "2026-09-29",
    priceHigh: 64,
    issueCr: 22,
    sub: 210.5,
    gmpPct: 62.0,
    listedPct: 90.0,
    score: 0.55,
  },
  {
    name: "Oakhaven Chemicals",
    board: "Mainboard",
    status: "listed",
    sector: "Chemicals",
    open: "2026-09-16",
    priceHigh: 482,
    issueCr: 1800,
    sub: 21.7,
    gmpPct: 18.0,
    listedPct: 14.3,
    score: 0.48,
  },
  {
    name: "Pebblecreek Dairy",
    board: "SME",
    status: "listed",
    sector: "FMCG",
    open: "2026-09-10",
    priceHigh: 45,
    issueCr: 12,
    sub: 0.9,
    gmpPct: -6.0,
    listedPct: -12.0,
    score: -0.58,
  },
];

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function verdictOf(score: number): IpoVerdict {
  if (score >= 0.3) return "positive";
  if (score <= -0.25) return "avoid";
  return "neutral";
}

function build(seed: Seed, i: number): Ipo {
  const rand = seeded(500 + i);
  const symbol = seed.name.split(" ")[0].toUpperCase().slice(0, 8);
  const closeDate = addDays(seed.open, 2);
  const allotmentDate = addDays(closeDate, 1);
  const listingDate = addDays(allotmentDate, 2);
  const priceLow = Math.round(seed.priceHigh * 0.95);
  const lotSize = Math.max(1, Math.round((seed.board === "SME" ? 120000 : 14800) / seed.priceHigh));
  const gmp = seed.gmpPct == null ? null : Math.round((seed.priceHigh * seed.gmpPct) / 100);
  const sub = seed.sub;
  const subByCategory =
    sub == null
      ? []
      : [
          { category: "QIB", times: Number((sub * (1.2 + rand() * 0.8)).toFixed(2)) },
          { category: "NII (HNI)", times: Number((sub * (0.6 + rand() * 0.8)).toFixed(2)) },
          { category: "Retail", times: Number((sub * (0.4 + rand() * 0.6)).toFixed(2)) },
          { category: "Employee", times: Number((sub * (0.2 + rand() * 0.5)).toFixed(2)) },
        ];
  const trendBase = seed.gmpPct ?? 0;
  const gmpTrend = Array.from({ length: 8 }, (_, d) => {
    const pct = trendBase * (0.55 + (d / 7) * 0.45) + (rand() - 0.5) * 2;
    return {
      date: addDays(seed.open, d - 5),
      gmp: Math.round((seed.priceHigh * pct) / 100),
    };
  });
  const revenue0 = seed.issueCr * (0.4 + rand() * 0.6) * 1e7;
  const financials = ["FY24", "FY25", "FY26"].map((year, y) => {
    const revenue = revenue0 * (1 + 0.18 * y + rand() * 0.05);
    const margin = seed.score > 0 ? 0.04 + 0.03 * y : 0.03 - 0.025 * y;
    return {
      year,
      revenue,
      profit: revenue * margin,
      netWorth: revenue * (0.5 + 0.08 * y),
    };
  });
  return {
    id: symbol.toLowerCase(),
    name: `${seed.name} Ltd`,
    symbol,
    board: seed.board,
    status: seed.status,
    sector: seed.sector,
    openDate: seed.open,
    closeDate,
    allotmentDate,
    listingDate,
    priceLow,
    priceHigh: seed.priceHigh,
    lotSize,
    issueSize: seed.issueCr * 1e7,
    freshPct: Math.round(30 + rand() * 60),
    subscription: sub,
    subByCategory,
    gmp,
    listedAt:
      seed.listedPct == null
        ? null
        : Number((seed.priceHigh * (1 + seed.listedPct / 100)).toFixed(2)),
    verdict: verdictOf(seed.score),
    score: seed.score,
    managers: i % 2 ? "Sample Capital, Example Securities" : "Placeholder Advisors",
    registrar: "Sample Registry Services Pvt Ltd",
    gmpTrend,
    financials,
    strengths: [
      `Revenue grew ~${Math.round(18 + rand() * 20)}% a year over the last three sample years.`,
      "Anchor book filled at the upper end of the price band.",
      `Priced at a ~${Math.round(10 + rand() * 20)}% discount to the sample peer group median P/E.`,
    ],
    risks: [
      "Large offer-for-sale portion: part of the money goes to existing holders, not the business.",
      `High customer concentration — top 5 clients are ~${Math.round(35 + rand() * 30)}% of revenue.`,
      "Grey market premium is unofficial and can reverse quickly before listing.",
    ],
    signals: [
      {
        name: "Subscription demand",
        value: sub == null ? "Not open yet" : `${sub.toFixed(2)}x`,
        score: clamp10(sub == null ? 5 : 3 + Math.log10(sub + 1) * 4),
        note: "Higher demand, especially from QIBs, tends to support listing price.",
      },
      {
        name: "Grey market premium",
        value:
          seed.gmpPct == null
            ? "No quotes"
            : `${seed.gmpPct > 0 ? "+" : ""}${seed.gmpPct.toFixed(1)}%`,
        score: clamp10(5 + (seed.gmpPct ?? 0) / 8),
        note: "Unofficial pre-listing trades. Indicative only.",
      },
      {
        name: "Valuation vs peers",
        value: `${(18 + rand() * 30).toFixed(1)}x P/E`,
        score: clamp10(5 + seed.score * 4 + (rand() - 0.5)),
        note: "Issue P/E compared with a sample listed-peer median.",
      },
      {
        name: "Financial trend",
        value: seed.score > 0 ? "Improving" : "Mixed",
        score: clamp10(5 + seed.score * 3 + rand()),
        note: "Three-year revenue and profit direction from the offer document.",
      },
      {
        name: "Lead manager record",
        value: `${Math.round(55 + rand() * 30)}% positive`,
        score: clamp10(5 + rand() * 4),
        note: "Share of the managers' recent issues that listed above the issue price.",
      },
    ],
    scoredAt: `${formatShort(closeDate)} 18:05 IST`,
  };
}

function clamp10(n: number): number {
  return Number(Math.max(1, Math.min(10, n)).toFixed(1));
}

function formatShort(iso: string): string {
  const [, m, d] = iso.split("-");
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${d} ${months[Number(m) - 1]}`;
}

export const ipos: Ipo[] = seeds.map(build);

export const ipoStats = {
  avgListingGain: 24.8,
  medianListingGain: 18.2,
  verdictAccuracy: 78.2,
  verdictHits: 82,
  verdictTotal: 105,
};

export const statusLabel: Record<IpoStatus, string> = {
  open: "Open",
  upcoming: "Upcoming",
  listed: "Listed",
  closed: "Closed",
};

export const verdictLabel: Record<IpoVerdict, string> = {
  positive: "Likely to do well",
  neutral: "Neutral / fair",
  avoid: "Avoid",
};

export function findIpo(id: string): Ipo {
  return ipos.find((ipo) => ipo.id === id) ?? ipos[0];
}

/** Estimated listing gain from GMP (or the actual gain once listed). */
export function listingGainPct(ipo: Ipo): number | null {
  if (ipo.listedAt != null) return ((ipo.listedAt - ipo.priceHigh) / ipo.priceHigh) * 100;
  if (ipo.gmp == null) return null;
  return (ipo.gmp / ipo.priceHigh) * 100;
}
