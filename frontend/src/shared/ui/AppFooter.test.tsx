import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";

import { AppFooter } from "./AppFooter";

it("provides branding, working resource links, legal links and a financial disclaimer", () => {
  render(<AppFooter />);
  const footer = within(screen.getByRole("contentinfo"));
  expect(footer.getByRole("link", { name: "Kash Engine home" })).toHaveAttribute("href", "/");
  const resources = within(footer.getByRole("navigation", { name: "Resources" }));
  for (const [name, href] of [
    ["About Kash Engine", "/"],
    ["API documentation", "/docs/"],
    ["Terms", "/legal/#terms"],
    ["Privacy", "/legal/#privacy"],
  ]) {
    expect(resources.getByRole("link", { name })).toHaveAttribute("href", href);
  }
  expect(footer.getByText(/Not financial advice/)).toHaveTextContent("GMP is unofficial");
  expect(footer.getByText(/\u00a9/)).toHaveTextContent(`${new Date().getFullYear()} Kash Engine`);
});
