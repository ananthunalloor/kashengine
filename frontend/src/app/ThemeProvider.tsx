import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <MantineProvider
      defaultColorScheme="light"
      theme={{
        respectReducedMotion: true,
        primaryColor: "violet",
        fontFamily: "var(--brand-font)",
        headings: { fontFamily: "var(--brand-font)", fontWeight: "650" },
        defaultRadius: "md",
      }}
      withCssVariables={false}
      withGlobalClasses={false}
    >
      {children}
    </MantineProvider>
  );
}
