export const uiStandard = {
  spacing: {
    xs: "var(--ui-space-2)",
    sm: "var(--ui-space-3)",
    md: "var(--ui-space-4)",
    lg: "var(--ui-space-5)",
    xl: "var(--ui-space-6)",
    xxl: "var(--ui-space-8)",
  },
  radius: {
    xs: "var(--ui-radius-sm)",
    sm: "var(--ui-radius-md)",
    md: "var(--ui-radius-lg)",
    lg: "var(--ui-radius-xl)",
    xl: "var(--ui-radius-xl)",
  },
  typography: {
    body: {
      size: "var(--ui-text-body-size)",
      lineHeight: 1.5,
    },
    label: {
      size: "var(--ui-text-label-size)",
      lineHeight: 1.4,
      weight: 600,
    },
    heading: {
      h1: { size: "var(--ui-heading-1-size)", lineHeight: 1.15, weight: 650 },
      h2: { size: "var(--ui-heading-2-size)", lineHeight: 1.2, weight: 650 },
      h3: { size: "var(--ui-heading-3-size)", lineHeight: 1.25, weight: 650 },
    },
  },
  controls: {
    button: {
      height: "var(--ui-button-height)",
      paddingInline: "var(--ui-button-padding-inline)",
      gap: "var(--ui-button-gap)",
      fontSize: "var(--ui-text-label-size)",
      fontWeight: 600,
    },
    icon: {
      sm: "var(--ui-icon-size-sm)",
      md: "var(--ui-icon-size-md)",
      lg: "var(--ui-icon-size-lg)",
    },
  },
} as const;
