export function displayNumber(value: string): number | null {
  const parsed = Number.parseFloat(value.replaceAll(",", "").replace("\u2212", "-"));
  return Number.isFinite(parsed) ? parsed : null;
}
