import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { OpsNotice } from "./OpsStatus";

it.each([
  ["success", "positive"],
  ["error", "negative"],
  ["warning", "warning"],
  ["info", "neutral"],
])("uses a labeled %s notice with a distinct status icon and tone", (level, tone) => {
  render(
    <ThemeProvider>
      <OpsNotice messages={[{ level, text: "Action feedback" }]} />
    </ThemeProvider>,
  );
  const status = screen.getByText(level);
  expect(status).toHaveClass(`ops-tone-${tone}`);
  expect(status.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  expect(screen.getByText("Action feedback")).toBeInTheDocument();
});
