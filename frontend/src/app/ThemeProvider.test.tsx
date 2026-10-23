import { Badge } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { ThemeProvider } from "./ThemeProvider";

it("applies shared compact tag styles to Mantine badges without changing their labels", () => {
  render(
    <ThemeProvider>
      <Badge color="gray">Holiday</Badge>
      <Badge color="blue">Special session</Badge>
    </ThemeProvider>,
  );

  for (const label of ["Holiday", "Special session"]) {
    expect(screen.getByText(label).closest(".app-status-tag")).toBeInTheDocument();
  }
});
