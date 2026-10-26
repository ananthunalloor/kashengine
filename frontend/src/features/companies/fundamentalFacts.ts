export type FundamentalFact = {
  label: string;
  value: unknown;
  comparison?: unknown;
};

export function humanize(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim();
}

export function collectFacts(value: unknown, path: string[] = []): FundamentalFact[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => {
      const rowName =
        item && typeof item === "object" && !Array.isArray(item) && typeof item.name === "string"
          ? item.name
          : `Record ${index + 1}`;
      return collectFacts(item, [...path, rowName]);
    });
  }
  if (!value || typeof value !== "object") return [];

  const record = value as Record<string, unknown>;
  if (typeof record.name === "string" && Object.hasOwn(record, "company_value")) {
    return [
      {
        label: record.name,
        value: record.company_value,
        ...(Object.hasOwn(record, "sector_value") ? { comparison: record.sector_value } : {}),
      },
    ];
  }
  return Object.entries(record).flatMap(([key, item]) => {
    if (key === "name" && typeof item === "string") return [];
    const label = [...path, humanize(key)].filter(Boolean).join(" · ");
    if (item === null || ["string", "number", "boolean"].includes(typeof item)) {
      return [{ label, value: item }];
    }
    return collectFacts(item, [...path, humanize(key)]);
  });
}

export function comparableNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const text = value.trim().replaceAll(",", "").replace(/%$/, "").trim();
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}
