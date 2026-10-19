import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { usePageTitle } from "./usePageTitle";

function Page({ title }: { title: string }) {
  usePageTitle(title);
  return (
    <main id="main">
      <h1>{title}</h1>
      <input aria-label="Search" />
    </main>
  );
}

it("updates the document title without focusing or making headings focusable", () => {
  const { rerender } = render(<Page title="Jobs" />);
  const heading = screen.getByRole("heading", { name: "Jobs" });
  expect(document.title).toBe("Jobs | Kash Engine");
  expect(heading).not.toHaveAttribute("tabindex");
  expect(heading).not.toHaveFocus();
  const input = screen.getByLabelText("Search");
  input.focus();
  rerender(<Page title="Task runs" />);
  expect(document.title).toBe("Task runs | Kash Engine");
  expect(input).toHaveFocus();
  expect(screen.getByRole("heading")).not.toHaveAttribute("tabindex");
});
