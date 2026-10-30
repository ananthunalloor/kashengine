import {
  DEFAULT_THEME,
  MantineThemeProvider,
  defaultCssVariablesResolver,
  mergeMantineTheme,
  useComputedColorScheme,
} from "@mantine/core";
import { useLayoutEffect } from "react";
import type { ReactNode } from "react";

import { palette, v2Theme } from "./theme";

const resolvedTheme = mergeMantineTheme(DEFAULT_THEME, v2Theme);
const base = defaultCssVariablesResolver(resolvedTheme);
const { slate, indigo, emerald, red, amber, sky, dark } = palette;

/** Compact control scale (32px controls, 28px micro buttons) shared by both schemes. */
const density: Record<string, string> = {
  "--button-height-sm": "2rem",
  "--button-padding-x-sm": "0.75rem",
  "--button-fz-sm": "13px",
  "--button-height-xs": "1.75rem",
  "--button-padding-x-xs": "0.5rem",
  "--button-fz-xs": "12px",
  "--button-height-compact-xs": "1.5rem",
  "--input-height-sm": "2rem",
  "--input-height-xs": "1.75rem",
  "--ai-size-input-sm": "2rem",
  "--ai-size-input-xs": "1.75rem",
  "--badge-height-sm": "1.25rem",
  "--badge-fz-sm": "11px",
  "--badge-padding-x-sm": "0.5rem",
  "--badge-height-xs": "1.125rem",
  "--badge-fz-xs": "10px",
};

const light: Record<string, string> = {
  "--mantine-color-body": "#ffffff",
  "--mantine-color-text": slate[8],
  "--mantine-color-dimmed": slate[5],
  "--mantine-color-placeholder": slate[4],
  "--mantine-color-anchor": indigo[6],
  "--mantine-color-default": "#ffffff",
  "--mantine-color-default-hover": slate[0],
  "--mantine-color-default-color": slate[8],
  "--mantine-color-default-border": slate[2],
  "--kv2-canvas": slate[0],
  "--kv2-surface": "#ffffff",
  "--kv2-surface-muted": slate[0],
  "--kv2-surface-sunken": slate[1],
  "--kv2-border": slate[2],
  "--kv2-border-strong": slate[3],
  "--kv2-text": slate[8],
  "--kv2-text-muted": slate[5],
  "--kv2-brand": indigo[6],
  "--kv2-brand-soft": indigo[0],
  "--kv2-gain": emerald[6],
  "--kv2-gain-soft": emerald[0],
  "--kv2-loss": red[6],
  "--kv2-loss-soft": red[0],
  "--kv2-caution": amber[6],
  "--kv2-caution-soft": amber[0],
  "--kv2-info": sky[6],
  "--kv2-info-soft": sky[0],
  "--kv2-neutral": slate[6],
  "--kv2-neutral-soft": slate[1],
  "--kv2-focus-ring": "#e0e7ff",
  "--kv2-terminal-bg": slate[9],
  "--kv2-terminal-text": slate[2],
};

const darkScheme: Record<string, string> = {
  "--mantine-color-body": dark[7],
  "--mantine-color-text": dark[0],
  "--mantine-color-dimmed": dark[2],
  "--mantine-color-placeholder": dark[3],
  "--mantine-color-anchor": indigo[4],
  "--mantine-color-default": dark[7],
  "--mantine-color-default-hover": dark[6],
  "--mantine-color-default-color": dark[0],
  "--mantine-color-default-border": dark[5],
  "--kv2-canvas": dark[9],
  "--kv2-surface": dark[7],
  "--kv2-surface-muted": dark[6],
  "--kv2-surface-sunken": dark[8],
  "--kv2-border": dark[5],
  "--kv2-border-strong": dark[4],
  "--kv2-text": dark[0],
  "--kv2-text-muted": dark[2],
  "--kv2-brand": indigo[4],
  "--kv2-brand-soft": "rgba(99, 102, 241, 0.16)",
  "--kv2-gain": emerald[3],
  "--kv2-gain-soft": "rgba(16, 185, 129, 0.12)",
  "--kv2-loss": red[3],
  "--kv2-loss-soft": "rgba(239, 68, 68, 0.12)",
  "--kv2-caution": amber[3],
  "--kv2-caution-soft": "rgba(245, 158, 11, 0.12)",
  "--kv2-info": sky[3],
  "--kv2-info-soft": "rgba(14, 165, 233, 0.12)",
  "--kv2-neutral": dark[2],
  "--kv2-neutral-soft": dark[5],
  "--kv2-focus-ring": "rgba(99, 102, 241, 0.35)",
  "--kv2-terminal-bg": dark[9],
  "--kv2-terminal-text": dark[1],
};

type Vars = Record<string, string>;
const shared: Vars = { ...(base.variables as Vars), ...density };
const schemes: Record<"light" | "dark", Vars> = {
  light: { ...(base.light as Vars), ...light },
  dark: { ...(base.dark as Vars), ...darkScheme },
};
const allKeys = new Set([
  ...Object.keys(shared),
  ...Object.keys(schemes.light),
  ...Object.keys(schemes.dark),
]);

/**
 * Activates the v2 design language for its subtree.
 *
 * The production CSP blocks injected `<style>` elements, so the resolved Mantine variables are
 * written to the `<html>` style attribute (allowed by `style-src-attr`) and removed on unmount.
 */
export function V2ThemeScope({ children }: { children: ReactNode }) {
  const scheme = useComputedColorScheme("light", { getInitialValueInEffect: false });

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.dataset.ui = "v2";
    for (const [key, value] of Object.entries({ ...shared, ...schemes[scheme] })) {
      root.style.setProperty(key, value);
    }
    return () => {
      delete root.dataset.ui;
      for (const key of allKeys) root.style.removeProperty(key);
    };
  }, [scheme]);

  return (
    <MantineThemeProvider theme={v2Theme} inherit={false}>
      {children}
    </MantineThemeProvider>
  );
}
