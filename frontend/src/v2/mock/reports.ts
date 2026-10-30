/*
 * Placeholder daily reports for the v2 Reports and Report detail pages. Every name, number and
 * story here is fictional sample data used only to exercise layouts.
 */
import { calendarSessions, companies, indices } from "./data";
import { seeded } from "./generate";

export type Outlook = "up" | "down" | "flat" | "na";
export type Outcome = "hit" | "miss" | "pending" | "na";

export type DeliveryAttempt = {
  id: string;
  time: string;
  channel: string;
  audience: string;
  result: "sent" | "failed";
  diagnostics: string;
};

export type IndexClose = {
  name: string;
  symbol: string;
  close: number;
  change: number;
  changePct: number;
};
export type ReportNews = {
  id: string;
  title: string;
  summary: string;
  source: string;
  score: number;
  companyIds: string[];
};
export type IpoWatch = {
  name: string;
  status: string;
  detail: string;
  tone: "gain" | "caution" | "info" | "neutral";
};
export type GlobalCue = { label: string; value: string; changePct: number; note: string };

export type DailyReport = {
  day: string;
  number: number;
  outlook: Outlook;
  strength: number;
  newsScore: number;
  globalScore: number;
  /** Observed change of the sample index on the report day; null while the session is pending. */
  actualPct: number | null;
  headline: string;
  summary: string;
  generatedAt: string;
  delivery: DeliveryAttempt[];
  indexCloses: IndexClose[];
  news: ReportNews[];
  ipos: IpoWatch[];
  globalCues: GlobalCue[];
};

/** Fixed "today" for the mock archive. */
export const LATEST_DAY = "2026-10-29";

const holidays = new Set(calendarSessions.filter((s) => s.type === "holiday").map((s) => s.date));

function isoOf(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function parseDay(day: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const date = new Date(`${day}T00:00:00Z`);
  return Number.isNaN(date.getTime()) || isoOf(date) !== day ? null : date;
}

export function isTradingDay(day: string): boolean {
  const date = parseDay(day);
  if (!date) return false;
  const dow = date.getUTCDay();
  return dow !== 0 && dow !== 6 && !holidays.has(day);
}

export function isValidDay(day: string): boolean {
  return parseDay(day) !== null;
}

function tradingDays(endDay: string, count: number): string[] {
  const out: string[] = [];
  const cursor = parseDay(endDay)!;
  while (out.length < count) {
    const iso = isoOf(cursor);
    if (isTradingDay(iso)) out.push(iso);
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return out;
}

function seedOf(day: string): number {
  return Number(day.replaceAll("-", ""));
}

const upHeadlines = [
  "Firm global cues and easing yields point to a positive open",
  "Broad buying in sample banks expected to lift the index",
  "Positive filings flow and steady liquidity support a rise",
  "Asia strength and softer crude favour an up session",
];
const downHeadlines = [
  "Weak overseas cues and firmer crude point to a soft start",
  "Profit-taking likely after a three-day rally in the sample index",
  "Rising sample volatility index signals a cautious, lower open",
];
const flatHeadlines = [
  "Mixed cues; range-bound trade likely ahead of sample data release",
  "Balanced news flow keeps the outlook neutral",
];

const newsTemplates = [
  {
    title: "{c} wins a sample order worth ₹{n} Cr",
    summary: "Order book visibility improves; the model reads this as a positive surprise.",
    score: 0.72,
  },
  {
    title: "{c} reports steady quarterly volumes",
    summary: "Numbers are in line with sample estimates; limited price impact expected.",
    score: 0.08,
  },
  {
    title: "Regulator issues notice to {c} over sample disclosure",
    summary: "Governance concern weighs on sentiment until the company responds.",
    score: -0.58,
  },
  {
    title: "{c} announces capacity expansion in sample region",
    summary: "Capex plan signals demand confidence; funding mix is still unclear.",
    score: 0.46,
  },
  {
    title: "{c} flags input-cost pressure for the coming quarter",
    summary: "Margin guidance trimmed; the article tone is clearly negative.",
    score: -0.41,
  },
  {
    title: "Sample central bank keeps policy rate unchanged",
    summary: "Status quo was expected; liquidity commentary reads mildly dovish.",
    score: 0.24,
  },
];

const sources = [
  "Sample Wire",
  "Example Business Daily",
  "Exchange filing (sample)",
  "Demo Markets Desk",
];

function buildReport(day: string, number: number, settled: boolean): DailyReport {
  const rand = seeded(seedOf(day));
  const roll = rand();
  const outlook: Outlook = roll < 0.52 ? "up" : roll < 0.8 ? "down" : roll < 0.95 ? "flat" : "na";
  const strength =
    outlook === "na"
      ? 0
      : Number((outlook === "flat" ? 3 + rand() * 2 : 4.5 + rand() * 4.5).toFixed(1));
  const hit = rand() < 0.72;
  const sign = outlook === "up" ? 1 : outlook === "down" ? -1 : 0;
  const magnitude = 0.25 + rand() * 1.1;
  let actualPct: number | null = null;
  if (settled) {
    if (outlook === "flat")
      actualPct = hit ? (rand() - 0.5) * 0.3 : (rand() < 0.5 ? -1 : 1) * magnitude;
    else if (outlook === "na") actualPct = (rand() - 0.5) * 1.6;
    else actualPct = (hit ? sign : -sign) * magnitude;
    actualPct = Number(actualPct.toFixed(2));
  }
  const pool = outlook === "up" ? upHeadlines : outlook === "down" ? downHeadlines : flatHeadlines;
  const headline =
    outlook === "na"
      ? "Not enough scored inputs to publish an outlook"
      : pool[Math.floor(rand() * pool.length)];

  const failedEmail = rand() < 0.12;
  const delivery: DeliveryAttempt[] =
    outlook === "na" && rand() < 0.5
      ? []
      : [
          {
            id: `${day}-tg`,
            time: "08:00",
            channel: "Telegram channel",
            audience: "1,840 members",
            result: "sent",
            diagnostics: "Message accepted · id tg-0001",
          },
          {
            id: `${day}-tgp`,
            time: "08:01",
            channel: "Telegram priority",
            audience: "212 members",
            result: "sent",
            diagnostics: "Message accepted · id tg-0002",
          },
          failedEmail
            ? {
                id: `${day}-em`,
                time: "08:02",
                channel: "Email digest",
                audience: "640 accounts",
                result: "failed",
                diagnostics: "Sample SMTP timeout after 30s · retry queued",
              }
            : {
                id: `${day}-em`,
                time: "08:02",
                channel: "Email digest",
                audience: "640 accounts",
                result: "sent",
                diagnostics: "Queued 640 · 0 bounces",
              },
        ];

  const indexCloses: IndexClose[] = indices.map((idx, i) => {
    const changePct = Number(
      ((actualPct ?? 0) * (i === 3 ? -2 : 1) + (rand() - 0.5) * 0.4).toFixed(2),
    );
    const close = Number((idx.last * (1 + ((rand() - 0.5) * 6) / 100)).toFixed(2));
    return {
      name: idx.name,
      symbol: idx.symbol,
      close,
      changePct,
      change: Number(((close * changePct) / 100).toFixed(2)),
    };
  });

  const news: ReportNews[] = [0, 1, 2].map((k) => {
    const template = newsTemplates[Math.floor(rand() * newsTemplates.length)];
    const company = companies[Math.floor(rand() * companies.length)];
    const second = companies[(companies.indexOf(company) + 3) % companies.length];
    return {
      id: `${day}-n${k}`,
      title: template.title
        .replace("{c}", company.name)
        .replace("{n}", String(200 + Math.floor(rand() * 4800))),
      summary: template.summary,
      source: sources[Math.floor(rand() * sources.length)],
      score: Number((template.score + (rand() - 0.5) * 0.2).toFixed(2)),
      companyIds: k === 0 ? [company.id, second.id] : [company.id],
    };
  });

  const ipos: IpoWatch[] = [
    {
      name: "Sample Logistics Ltd",
      status: "Day 2 · Open",
      detail: `Subscribed ${(1 + rand() * 6).toFixed(2)}x overall (sample)`,
      tone: "info",
    },
    {
      name: "Demo Cloud Data Ltd",
      status: rand() < 0.5 ? "Listing today" : "Allotment",
      detail: "Issue price ₹380 · sample indicative band ₹400–₹430",
      tone: "gain",
    },
    {
      name: "Placeholder Foods Ltd",
      status: "Opens next week",
      detail: "Price band ₹112–₹118 · lot size 125 (sample)",
      tone: "neutral",
    },
  ];

  const globalCues: GlobalCue[] = [
    {
      label: "Sample US Index",
      value: (5800 + rand() * 300).toFixed(1),
      changePct: Number(((rand() - 0.4) * 1.4).toFixed(2)),
      note: "Overnight close",
    },
    {
      label: "Sample Asia Index",
      value: (38000 + rand() * 1500).toFixed(1),
      changePct: Number(((rand() - 0.45) * 1.6).toFixed(2)),
      note: "Morning trade",
    },
    {
      label: "Sample crude ($/bbl)",
      value: (68 + rand() * 12).toFixed(2),
      changePct: Number(((rand() - 0.5) * 2.4).toFixed(2)),
      note: "Lower is favourable",
    },
    {
      label: "Sample 10Y yield",
      value: `${(4 + rand() * 0.5).toFixed(2)}%`,
      changePct: Number(((rand() - 0.5) * 1.2).toFixed(2)),
      note: "Lower is favourable",
    },
    {
      label: "USD / INR (sample)",
      value: (83 + rand() * 1.5).toFixed(2),
      changePct: Number(((rand() - 0.5) * 0.4).toFixed(2)),
      note: "Rupee move",
    },
  ];

  const summary =
    outlook === "na"
      ? "Fewer than the minimum number of scored articles were available before the cut-off, so no outlook was published. Index and news sections are shown for reference only."
      : `The model expects the Sample Index 50 to ${outlook === "up" ? "rise" : outlook === "down" ? "fall" : "stay flat"} today with ${strength >= 7 ? "strong" : strength >= 5 ? "moderate" : "weak"} conviction (${strength.toFixed(1)} / 10). ${headline}. Watch the opening 30 minutes for confirmation before acting on this sample outlook.`;

  return {
    day,
    number,
    outlook,
    strength,
    newsScore: Number((3 + rand() * 6).toFixed(1)),
    globalScore: Number((3 + rand() * 6).toFixed(1)),
    actualPct,
    headline,
    summary,
    generatedAt: `07:${String(40 + Math.floor(rand() * 15)).padStart(2, "0")}`,
    delivery,
    indexCloses,
    news,
    ipos,
    globalCues,
  };
}

const ARCHIVE_SIZE = 84;

/** Newest first. The latest report's session has not settled yet. */
export const reports: DailyReport[] = tradingDays(LATEST_DAY, ARCHIVE_SIZE).map((day, i) =>
  buildReport(day, 482 - i, i !== 0),
);

export function outcomeOf(report: DailyReport): Outcome {
  if (report.outlook === "na") return "na";
  if (report.actualPct == null) return "pending";
  const actual = Math.abs(report.actualPct) < 0.2 ? "flat" : report.actualPct > 0 ? "up" : "down";
  return actual === report.outlook ? "hit" : "miss";
}

/** Look up a report; valid dates outside the archive get a generated sample. */
export function reportFor(day: string): { report: DailyReport; fallback: boolean } {
  const found = reports.find((r) => r.day === day);
  if (found) return { report: found, fallback: false };
  if (isValidDay(day) && day <= LATEST_DAY && isTradingDay(day)) {
    return { report: buildReport(day, 0, true), fallback: false };
  }
  return { report: reports[0], fallback: true };
}

/** Nearest archived reports before and after a day (archive is newest first). */
export function neighbours(day: string): { older?: DailyReport; newer?: DailyReport } {
  const older = reports.find((r) => r.day < day);
  const newer = [...reports].reverse().find((r) => r.day > day);
  return { older, newer };
}

const outlookWord: Record<Outlook, string> = {
  up: "RISE ▲",
  down: "FALL ▼",
  flat: "FLAT –",
  na: "NOT AVAILABLE",
};

/** The plain-text version exactly as delivered to Telegram / email. */
export function plainText(report: DailyReport, dayLabel: string): string {
  const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
  const lines = [
    `KASH ENGINE · DAILY BRIEF · ${dayLabel.toUpperCase()} (SAMPLE)`,
    "",
    `Outlook: ${outlookWord[report.outlook]}${report.outlook === "na" ? "" : `  ·  Strength ${report.strength.toFixed(1)}/10`}`,
    report.headline,
    "",
    "INDEX CLOSES (previous session)",
    ...report.indexCloses.map(
      (i) => `  ${i.name.padEnd(20)} ${i.close.toFixed(2).padStart(10)}  ${pct(i.changePct)}`,
    ),
    "",
    "KEY NEWS",
    ...report.news.map((n) => `  ${n.score >= 0 ? "+" : ""}${n.score.toFixed(2)}  ${n.title}`),
    "",
    "IPO WATCH",
    ...report.ipos.map((i) => `  ${i.name} — ${i.status}`),
    "",
    "GLOBAL CUES",
    ...report.globalCues.map((g) => `  ${g.label}: ${g.value} (${pct(g.changePct)})`),
    "",
    "Sample data · not investment advice.",
  ];
  return lines.join("\n");
}
