import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <MantineProvider
      defaultColorScheme="auto"
      theme={{ respectReducedMotion: true }}
      withCssVariables={false}
      withGlobalClasses={false}
    >
      {children}
    </MantineProvider>
  );
}
