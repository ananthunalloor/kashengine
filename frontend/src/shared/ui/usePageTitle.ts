import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | Kash Engine`;
    document.querySelector<HTMLElement>("#main h1")?.focus();
  }, [title]);
}
