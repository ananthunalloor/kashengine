const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const inrInt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹1,23,456.78 (Indian digit grouping). */
export function formatInr(value: number | null | undefined, { decimals = 2 } = {}): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `₹${decimals === 0 ? inrInt.format(value) : inr.format(value)}`;
}

/** 1,23,456 without currency. */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(value);
}

/** ₹12.4 L / ₹1,240 Cr. */
export function formatCompactInr(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e7) return `₹${formatNumber(value / 1e7, abs >= 1e9 ? 0 : 1)} Cr`;
  if (abs >= 1e5) return `₹${formatNumber(value / 1e5, 1)} L`;
  return formatInr(value, { decimals: 0 });
}

/** +1.24% / -0.80% / 0.00%. */
export function formatPercent(
  value: number | null | undefined,
  { signed = true, decimals = 2 } = {},
) {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function formatSigned(value: number | null | undefined, decimals = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, decimals)}`;
}

export type Direction = "up" | "down" | "flat";

export function directionOf(value: number | null | undefined, epsilon = 0.005): Direction {
  if (value == null || Math.abs(value) < epsilon) return "flat";
  return value > 0 ? "up" : "down";
}

export const directionGlyph: Record<Direction, string> = { up: "▲", down: "▼", flat: "–" };

const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "12 Mar 2025" from an ISO date (yyyy-mm-dd). Avoids timezone shifts by parsing parts. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${String(d).padStart(2, "0")} ${months[m - 1]} ${y}`;
}

/** "12 Mar 2025, 09:15 IST" from an ISO date + HH:mm time. */
export function formatDateTime(iso: string, time: string): string {
  return `${formatDate(iso)}, ${time} IST`;
}
