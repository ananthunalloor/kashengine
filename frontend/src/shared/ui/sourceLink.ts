export function sourceLink(url: string): string | undefined {
  if (!URL.canParse(url)) return undefined;
  return ["https:", "http:"].includes(new URL(url).protocol) ? url : undefined;
}
