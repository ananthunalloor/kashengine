import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { SkipLink } from "./SkipLink";

it("retains a focusable keyboard skip link targeting the main content", () => {
  render(
    <>
      <SkipLink />
      <main id="main" tabIndex={-1}>
        Content
      </main>
    </>,
  );
  const link = screen.getByRole("link", { name: "Skip to the content" });
  expect(link).toHaveAttribute("href", "#main");
  expect(link).not.toHaveAttribute("tabindex", "-1");
  link.focus();
  expect(link).toHaveFocus();
});
