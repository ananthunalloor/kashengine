/*
 * Placeholder data for the v2 Account and Delivery pages. All names, addresses, tokens and
 * handles are fictional sample values.
 */

export const profile = {
  name: "Sample User",
  username: "sample.user",
  email: "user@example.com",
  emailVerified: false,
  memberSince: "2025-03-14",
  timezone: "Asia/Kolkata (IST)",
};

export type PlanState = "none" | "trial" | "active" | "expired" | "staff";

export const subscription = {
  state: "active" as PlanState,
  plan: "Sample Pro",
  price: 1499,
  period: "month",
  currency: "INR",
  started: "2025-11-12",
  ends: "2026-02-12",
  daysRemaining: 31,
};

export type Feature = {
  name: string;
  help: string;
  access: "included" | "not-on-account" | "locked";
};

export const features: Feature[] = [
  {
    name: "Today dashboard",
    help: "Daily outlook, market movers and the morning brief.",
    access: "included",
  },
  {
    name: "Scored news",
    help: "Articles scored for sentiment and relevance per company.",
    access: "included",
  },
  {
    name: "Daily reports",
    help: "Full report archive with prediction review.",
    access: "included",
  },
  { name: "IPO scores", help: "Scorecards for open and upcoming sample IPOs.", access: "included" },
  { name: "Live quotes", help: "Streaming prices and market depth.", access: "locked" },
  { name: "API access", help: "Read-only REST API with personal tokens.", access: "included" },
  { name: "Ops console", help: "Staff-only operations area.", access: "not-on-account" },
];

export type ApiToken = {
  id: string;
  name: string;
  suffix: string;
  created: string;
  lastUsed: string | null;
  ends: string;
  state: "active" | "expired" | "revoked";
};

export const apiTokens: ApiToken[] = [
  {
    id: "t1",
    name: "Sample notebook",
    suffix: "a91f",
    created: "2025-12-02",
    lastUsed: "2026-01-12",
    ends: "2026-06-02",
    state: "active",
  },
  {
    id: "t2",
    name: "Example dashboard",
    suffix: "7c20",
    created: "2025-10-18",
    lastUsed: "2026-01-09",
    ends: "2026-04-18",
    state: "active",
  },
  {
    id: "t3",
    name: "Old test script",
    suffix: "03be",
    created: "2025-05-01",
    lastUsed: "2025-08-30",
    ends: "2025-11-01",
    state: "expired",
  },
];

export type Session = {
  id: string;
  device: string;
  kind: "desktop" | "mobile";
  location: string;
  lastActive: string;
  current: boolean;
};

export const sessions: Session[] = [
  {
    id: "s1",
    device: "Browser on desktop",
    kind: "desktop",
    location: "Sample City",
    lastActive: "Active now",
    current: true,
  },
  {
    id: "s2",
    device: "Browser on phone",
    kind: "mobile",
    location: "Sample City",
    lastActive: "Today, 08:12 IST",
    current: false,
  },
  {
    id: "s3",
    device: "Browser on laptop",
    kind: "desktop",
    location: "Example Town",
    lastActive: "09 Jan 2026, 19:40 IST",
    current: false,
  },
];

export type ChannelKind = "email" | "telegram";
export type DeliveryStatus = "sent" | "failed" | "retrying";

export type DeliveryAttempt = {
  id: string;
  date: string;
  time: string;
  channel: ChannelKind;
  target: string;
  report: string;
  status: DeliveryStatus;
  latencyMs: number;
  detail: string;
};

export const telegramSample = { handle: "@sample_brief_bot", chat: "Sample chat" };

const reportDays = [
  "2026-01-12",
  "2026-01-09",
  "2026-01-08",
  "2026-01-07",
  "2026-01-06",
  "2026-01-05",
  "2026-01-02",
];

export const deliveryLog: DeliveryAttempt[] = reportDays.flatMap((date, i) => {
  const emailFailed = i === 3;
  const tgRetry = i === 5;
  return [
    {
      id: `${date}-email`,
      date,
      time: `08:0${(i % 3) + 1}`,
      channel: "email" as const,
      target: "user@example.com",
      report: date,
      status: emailFailed ? ("failed" as const) : ("sent" as const),
      latencyMs: 1400 + ((i * 137) % 600),
      detail: emailFailed ? "Mailbox temporarily unavailable (sample bounce)" : "Delivered",
    },
    {
      id: `${date}-telegram`,
      date,
      time: `08:0${(i % 3) + 1}`,
      channel: "telegram" as const,
      target: "Sample chat",
      report: date,
      status: tgRetry ? ("retrying" as const) : ("sent" as const),
      latencyMs: 380 + ((i * 53) % 200),
      detail: tgRetry ? "Rate limited, retry 1 of 3 scheduled" : "Delivered",
    },
  ];
});

deliveryLog.unshift({
  id: "test-1",
  date: "2026-01-12",
  time: "10:15",
  channel: "telegram",
  target: "Sample chat",
  report: "Test",
  status: "sent",
  latencyMs: 412,
  detail: "Test message delivered",
});
