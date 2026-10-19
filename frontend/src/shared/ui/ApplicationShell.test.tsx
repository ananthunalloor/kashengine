import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { session } from "../../test/session";
import { ThemeProvider } from "../../app/ThemeProvider";
import type { Session } from "../api/generated/types.gen";
import { ApplicationShell } from "./ApplicationShell";

function showShell(value: Session = session) {
  return render(
    <ThemeProvider>
      <ApplicationShell session={value}>
        <h1>Preview</h1>
      </ApplicationShell>
    </ThemeProvider>,
  );
}

it("renders the server-provided links without inventing access", () => {
  showShell();
  expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/app/reports/");
  expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/app/dashboard/");
  expect(screen.queryByRole("link", { name: "News" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ops" })).not.toBeInTheDocument();
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("shows subscription notices and keeps account navigation for locked users", () => {
  showShell({
    ...session,
    features: [],
    subscription_ok: false,
    subscription_state: "expired",
    notice: "Your access has ended.",
    navigation: [{ label: "Account", url: "/account/" }],
  });
  expect(screen.getByRole("status")).toHaveTextContent("Your access has ended.");
  expect(screen.queryByRole("link", { name: "Reports" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/app/account/");
});

it("uses a CSRF-protected POST for logout", () => {
  document.cookie = "csrftoken=shell-csrf; path=/";
  showShell();
  const button = screen.getByRole("button", { name: "Log out" });
  const form = button.closest("form");
  expect(form).toHaveAttribute("method", "post");
  expect(form).toHaveAttribute("action", "/logout/");
  expect(form?.querySelector("input")).toHaveValue("shell-csrf");
  expect(button).toBeEnabled();
  document.cookie = "csrftoken=; Max-Age=0; path=/";
});

it("exposes the mobile navigation toggle state and supports a theme toggle", () => {
  showShell();
  fireEvent.click(screen.getByRole("button", { name: "Open navigation", hidden: true }));
  expect(screen.getByRole("button", { name: "Close navigation", hidden: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  fireEvent.keyDown(screen.getByRole("navigation", { name: "Main" }), { key: "Escape" });
  expect(screen.getByRole("button", { name: "Open navigation", hidden: true })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Toggle color scheme" }));
  expect(document.documentElement).toHaveAttribute("data-mantine-color-scheme", "dark");
  expect(document.querySelector("style")).toBeNull();
});
