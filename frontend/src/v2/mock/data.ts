/*
 * Placeholder data for the v2 mock pages. Every name, symbol and number here is fictional and
 * exists only to exercise layouts. Replace with API queries during the migration.
 */
import { mockSeries } from "./generate";

export const sampleUser = {
  name: "Sample User",
  initials: "SU",
  email: "user@example.com",
  staff: true,
};

export const marketStatus = {
  open: true,
  label: "NSE open",
  detail: "closes 15:30 IST",
  asOf: "12 Jan 2026, 11:42 IST",
};

export type IndexQuote = {
  symbol: string;
  name: string;
  last: number;
  change: number;
  changePct: number;
  trend: number[];
};

export const indices: IndexQuote[] = [
  {
    symbol: "IDX50",
    name: "Sample Index 50",
    last: 24311.2,
    change: 142.3,
    changePct: 0.59,
    trend: mockSeries(30, 24000, 11, 0.02),
  },
  {
    symbol: "IDX30",
    name: "Sample Index 30",
    last: 79845.6,
    change: 489.15,
    changePct: 0.61,
    trend: mockSeries(30, 79000, 12, 0.02),
  },
  {
    symbol: "BANKX",
    name: "Sample Bank Index",
    last: 52190.45,
    change: -114.2,
    changePct: -0.22,
    trend: mockSeries(30, 52400, 13, -0.03),
  },
  {
    symbol: "VOLX",
    name: "Sample Volatility",
    last: 12.84,
    change: -0.32,
    changePct: -2.43,
    trend: mockSeries(30, 13.4, 14, -0.04),
  },
];

export type Company = {
  id: string;
  symbol: string;
  name: string;
  sector: string;
  last: number;
  changePct: number;
  marketCap: number;
  pe: number;
  deliveryPct: number;
  volume: number;
  signal: "Accumulation" | "Distribution" | "Neutral";
  trend: number[];
};

const sectors = [
  "Energy",
  "Banking",
  "IT Services",
  "FMCG",
  "Autos",
  "Pharma",
  "Metals",
  "Telecom",
];
const names = [
  "Acme Industries",
  "Bluefin Bank",
  "Cobalt Systems",
  "Delta Foods",
  "Everest Motors",
  "Fernhill Pharma",
  "Granite Metals",
  "Horizon Telecom",
  "Indigo Power",
  "Juniper Finance",
  "Kestrel Software",
  "Lotus Consumer",
  "Meridian Auto Parts",
  "Northstar Labs",
  "Orchid Steel",
  "Pinecrest Networks",
  "Quartz Energy",
  "Redwood Capital",
  "Saffron Brands",
  "Tidewater Logistics",
  "Umber Chemicals",
  "Vertex Infotech",
  "Willow Healthcare",
  "Zenith Cement",
];

export const companies: Company[] = names.map((name, i) => {
  const symbol = name
    .split(" ")
    .map((w) => w.slice(0, i % 2 ? 3 : 4))
    .join("")
    .toUpperCase()
    .slice(0, 8);
  const changePct = Number(((((i * 37) % 11) - 5) / 2.1).toFixed(2));
  return {
    id: symbol.toLowerCase(),
    symbol,
    name,
    sector: sectors[i % sectors.length],
    last: 250 + ((i * 7919) % 4200) + 0.45,
    changePct,
    marketCap: (5 + ((i * 131) % 190)) * 1e10,
    pe: 12 + ((i * 17) % 40),
    deliveryPct: 35 + ((i * 23) % 45),
    volume: 4e5 + ((i * 104729) % 9e6),
    signal: i % 3 === 0 ? "Accumulation" : i % 3 === 1 ? "Neutral" : "Distribution",
    trend: mockSeries(24, 100, 100 + i, changePct / 50),
  };
});

export type CalendarSession = {
  date: string;
  type: "holiday" | "special";
  name: string;
  hours: string;
};

export const calendarSessions: CalendarSession[] = [
  { date: "2026-01-26", type: "holiday", name: "Sample holiday A", hours: "Closed" },
  { date: "2026-03-03", type: "holiday", name: "Sample holiday B", hours: "Closed" },
  { date: "2026-04-03", type: "holiday", name: "Sample holiday C", hours: "Closed" },
  { date: "2026-04-14", type: "holiday", name: "Sample holiday D", hours: "Closed" },
  { date: "2026-05-01", type: "holiday", name: "Sample holiday E", hours: "Closed" },
  { date: "2026-08-26", type: "holiday", name: "Sample holiday F", hours: "Closed" },
  { date: "2026-10-02", type: "holiday", name: "Sample holiday G", hours: "Closed" },
  { date: "2026-10-20", type: "holiday", name: "Sample holiday H", hours: "Closed" },
  {
    date: "2026-11-12",
    type: "special",
    name: "Sample evening session",
    hours: "18:15 – 19:15 IST",
  },
  { date: "2026-11-13", type: "holiday", name: "Sample holiday I", hours: "Closed" },
  { date: "2026-12-25", type: "holiday", name: "Sample holiday J", hours: "Closed" },
];

export type Notice = {
  id: string;
  title: string;
  time: string;
  tone: "gain" | "loss" | "caution" | "info";
};

export const notifications: Notice[] = [
  { id: "n1", title: "Daily brief for 12 Jan is ready", time: "08:05 IST", tone: "info" },
  { id: "n2", title: "Outlook updated: Sample Index 50 ▲ Rise", time: "08:00 IST", tone: "gain" },
  { id: "n3", title: "Sample IPO subscription closes today", time: "Yesterday", tone: "caution" },
];
