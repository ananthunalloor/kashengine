/*
 * Placeholder content for the v2 public pages (landing, auth). Every name and number here is
 * fictional sample data used only to illustrate the layout.
 */
import { mockSeries } from "./generate";

export const sampleBrief = {
  date: "2026-01-12",
  edition: "06:30 IST",
  outlook: {
    direction: "up" as const,
    label: "Positive signal",
    strength: 6.8,
    note: "Overnight global cues and broadly positive news flow lean slightly upward. Low conviction — treat as context, not a call.",
  },
  closes: [
    { symbol: "IDX50", name: "Sample Index 50", last: 24311.2, changePct: 0.59 },
    { symbol: "IDX30", name: "Sample Index 30", last: 79845.6, changePct: 0.61 },
    { symbol: "BANKX", name: "Sample Bank Index", last: 52190.45, changePct: -0.22 },
  ],
  news: [
    {
      id: "n1",
      company: "Acme Industries",
      headline: "Acme Industries reports higher quarterly order book",
      reason: "New orders and steady margins mentioned in the filing.",
      score: 0.62,
    },
    {
      id: "n2",
      company: "Globex Power",
      headline: "Globex Power commissions new sample plant ahead of schedule",
      reason: "Earlier-than-planned capacity addition.",
      score: 0.38,
    },
    {
      id: "n3",
      company: "Initech Motors",
      headline: "Initech Motors flags higher input costs for the quarter",
      reason: "Management expects margin pressure in the near term.",
      score: -0.41,
    },
  ],
};

export type Capability = {
  key: string;
  title: string;
  body: string;
  tags: [string, string];
};

export const capabilities: Capability[] = [
  {
    key: "news",
    title: "News with a point of view",
    body: "Each morning's news is scored from −1 to +1 by a local AI model, with a short reason so you can see why.",
    tags: ["Sentiment score", "Plain-language reason"],
  },
  {
    key: "outlook",
    title: "A more informed outlook",
    body: "A daily direction estimate for the benchmark index before the open, checked against the actual close afterwards.",
    tags: ["Pre-open estimate", "Checked every session"],
  },
  {
    key: "ipos",
    title: "IPOs, beyond the buzz",
    body: "Upcoming and recent issues with key dates, subscription figures and a transparent score you can inspect.",
    tags: ["Mainboard & SME", "Score breakdown"],
  },
  {
    key: "companies",
    title: "Know the companies",
    body: "A company directory with fundamentals, price charts and related news in one place.",
    tags: ["Fundamentals", "Charts & news"],
  },
  {
    key: "brief",
    title: "Your daily market brief",
    body: "Outlook, index closes, scored news and IPO updates combined into one short report.",
    tags: ["One page", "Every trading day"],
  },
  {
    key: "delivery",
    title: "From the engine to you",
    body: "Read it on the web, get it by email or Telegram, or pull the data through a read-only API.",
    tags: ["Email & Telegram", "Read-only API"],
  },
];

export const steps = [
  {
    title: "Collect the signals",
    body: "News, exchange announcements and global market moves are gathered overnight.",
  },
  {
    title: "Connect the context",
    body: "A local AI model scores each item and combines the signals into a daily outlook.",
  },
  {
    title: "Start with the big picture",
    body: "You get one brief before the open — then make your own decisions.",
  },
];

export const trackRecord = {
  windowSessions: 60,
  hits: 37,
  accuracy: 61.7,
  baseline: 52.0,
  // Rolling 20-session hit rate (sample values).
  rolling: mockSeries(40, 58, 21, 0.01).map((value, index) => ({
    session: `S${index + 1}`,
    accuracy: Math.max(45, Math.min(72, Number(value.toFixed(1)))),
    baseline: 52,
  })),
};

export const channels = [
  { key: "web", title: "Web dashboard", body: "Full brief, charts and history in the browser." },
  { key: "email", title: "Email", body: "The morning brief in your inbox before the open." },
  {
    key: "telegram",
    title: "Telegram",
    body: "A short summary message with a link to the full report.",
  },
  { key: "api", title: "Read-only API", body: "The same data as JSON for your own tools." },
];
