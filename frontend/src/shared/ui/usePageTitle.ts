import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | Kash Engine`;
    if (document.activeElement?.matches("input, select, textarea")) return;
    document.querySelector<HTMLElement>("#main h1")?.focus();
  }, [title]);
}
