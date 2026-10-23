import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Grid,
  Group,
  MantineProvider,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
  createTheme,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import type { ReactNode } from "react";

import { uiStandard } from "./uiStandard";

const appTheme = createTheme({
  respectReducedMotion: true,
  primaryColor: "violet",
  fontFamily: "var(--brand-font)",
  headings: { fontFamily: "var(--brand-font)", fontWeight: "650" },
  defaultRadius: 0,
  cursorType: "pointer",
  spacing: uiStandard.spacing,
  radius: uiStandard.radius,
  lineHeights: {
    xs: "1.4",
    sm: "1.45",
    md: "1.5",
    lg: "1.6",
    xl: "1.7",
  },
  fontSizes: {
    xs: "var(--ui-text-xs-size)",
    sm: "var(--ui-text-label-size)",
    md: "var(--ui-text-body-size)",
    lg: "var(--ui-text-lg-size)",
    xl: "var(--ui-text-xl-size)",
  },
  components: {
    Stack: Stack.extend({ defaultProps: { gap: "md" } }),
    Group: Group.extend({ defaultProps: { gap: "sm" } }),
    SimpleGrid: SimpleGrid.extend({ defaultProps: { spacing: "md", verticalSpacing: "md" } }),
    Grid: Grid.extend({ defaultProps: { gutter: "md" } }),
    Paper: Paper.extend({ defaultProps: { p: "md", radius: "sm" } }),
    Card: Card.extend({ defaultProps: { padding: "md", radius: "sm" } }),
    Button: Button.extend({
      defaultProps: {
        radius: "sm",
        size: "sm",
      },
      styles: {
        root: {
          minHeight: uiStandard.controls.button.height,
          paddingInline: uiStandard.controls.button.paddingInline,
          gap: uiStandard.controls.button.gap,
          fontSize: uiStandard.controls.button.fontSize,
          fontWeight: uiStandard.controls.button.fontWeight,
        },
        section: {
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        },
      },
    }),
    ActionIcon: ActionIcon.extend({
      defaultProps: {
        size: "md",
      },
      styles: {
        root: {
          width: uiStandard.controls.button.height,
          height: uiStandard.controls.button.height,
        },
      },
    }),
    TextInput: TextInput.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    DateInput: DateInput.extend({
      defaultProps: {
        size: "sm",
        radius: "sm",
        ariaLabels: {
          nextMonth: "Next month",
          previousMonth: "Previous month",
          nextYear: "Next year",
          previousYear: "Previous year",
          nextDecade: "Next decade",
          previousDecade: "Previous decade",
        },
      },
    }),
    Select: Select.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    Textarea: Textarea.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    NumberInput: NumberInput.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    PasswordInput: PasswordInput.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    Checkbox: Checkbox.extend({ defaultProps: { size: "sm", radius: "sm" } }),
    Switch: Switch.extend({ defaultProps: { size: "sm" } }),
    Badge: Badge.extend({
      defaultProps: { size: "sm", radius: "sm" },
      classNames: { root: "app-status-tag" },
    }),
    Alert: Alert.extend({ defaultProps: { radius: "sm", p: "md" } }),
    Modal: Modal.extend({ defaultProps: { radius: "sm", padding: "lg" } }),
    Table: Table.extend({ defaultProps: { verticalSpacing: "sm", horizontalSpacing: "md" } }),
    Text: Text.extend({
      defaultProps: {
        size: "md",
      },
      styles: {
        root: {
          lineHeight: uiStandard.typography.body.lineHeight,
        },
      },
    }),
    Title: Title.extend({
      defaultProps: {
        order: 2,
      },
      styles: {
        root: {
          lineHeight: 1.2,
          letterSpacing: "0",
        },
      },
    }),
  },
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <MantineProvider
      defaultColorScheme="light"
      theme={appTheme}
      withCssVariables={false}
      withGlobalClasses={false}
    >
      {children}
    </MantineProvider>
  );
}
