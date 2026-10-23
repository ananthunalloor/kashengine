import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

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
  expect(screen.getByRole("link", { name: "Reports" })).toHaveAttribute("href", "/reports/");
  expect(screen.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/dashboard/");
  expect(screen.queryByRole("link", { name: "News" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ops" })).not.toBeInTheDocument();
  expect(screen.queryByText("Workspace", { exact: true })).not.toBeInTheDocument();
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("shows ops categories in the sidebar and page options as tabs", () => {
  render(
    <ThemeProvider>
      <ApplicationShell
        session={{ ...session, is_staff: true, is_superuser: true }}
        pathname="/ops/jobs/"
      >
        <h1>Jobs preview</h1>
      </ApplicationShell>
    </ThemeProvider>,
  );

  expect(screen.getByRole("navigation", { name: "Operations options" })).toBeInTheDocument();
  const activityLink = screen.getByRole("link", { name: "Activity" });
  expect(activityLink).toHaveAttribute("href", "/ops/");
  expect(activityLink).not.toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("href", "/ops/");
  expect(screen.getByRole("tab", { name: "Jobs" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("heading", { name: "Jobs preview" })).toBeInTheDocument();
});

it("shows the tabs buffer only while pinned and clears it when scrolling back", () => {
  const view = render(
    <ThemeProvider>
      <ApplicationShell session={{ ...session, is_staff: true }} pathname="/ops/jobs/">
        <h1>Jobs preview</h1>
      </ApplicationShell>
    </ThemeProvider>,
  );
  const tabs = screen.getByRole("tablist", { name: "Activity pages" });
  tabs.style.top = "64px";
  const bounds = vi.spyOn(tabs, "getBoundingClientRect");
  bounds.mockReturnValue(new DOMRect(0, 120, 300, 40));
  fireEvent.scroll(window);
  expect(tabs).toHaveAttribute("data-stuck", "false");
  bounds.mockReturnValue(new DOMRect(0, 64, 300, 40));
  fireEvent.scroll(window);
  expect(tabs).toHaveAttribute("data-stuck", "true");
  bounds.mockReturnValue(new DOMRect(0, 120, 300, 40));
  fireEvent.scroll(window);
  expect(tabs).toHaveAttribute("data-stuck", "false");
  view.unmount();
  bounds.mockRestore();
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
  expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account/");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss account notice" }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Account" })).toBeInTheDocument();
});

it("uses a CSRF-protected POST for logout", () => {
  document.cookie = "csrftoken=shell-csrf; path=/";
  showShell();
  fireEvent.click(screen.getByRole("button", { name: "Account menu for member" }));
  const button = screen.getByRole("button", { name: "Log out" });
  const form = button.closest("form");
  expect(form).toHaveAttribute("method", "post");
  expect(form).toHaveAttribute("action", "/logout/");
  expect(form?.querySelector("input")).toHaveValue("shell-csrf");
  expect(form?.querySelector('input[name="next"]')).toHaveValue("/login/");
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
  expect(screen.getByRole("button", { name: "Toggle color scheme" }).textContent).toBe("");
  expect(screen.getByRole("button", { name: "Toggle color scheme" })).toHaveAttribute(
    "title",
    "Switch to light theme",
  );
  expect(document.documentElement).toHaveAttribute("data-mantine-color-scheme", "dark");
  fireEvent.click(screen.getByRole("button", { name: "Toggle color scheme" }));
  expect(document.documentElement).toHaveAttribute("data-mantine-color-scheme", "light");
  expect(document.querySelector("style")).toBeNull();
});

it("shows account identity and details in a keyboard-dismissable popover", () => {
  showShell();
  const trigger = screen.getByRole("button", { name: "Account menu for member" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  expect(trigger).toHaveAttribute("aria-expanded", "true");
  const popover = screen.getByRole("dialog", { name: "Your account" });
  expect(popover).toHaveTextContent("member@example.test");
  expect(popover).toHaveTextContent("Member");
  expect(popover).toHaveTextContent("Trial");
  expect(popover).toHaveTextContent("A subscription is not currently required.");
  const link = screen.getByRole("link", { name: "Account details" });
  expect(link).toHaveAttribute("href", "/account/");
  expect(link).toHaveFocus();
  fireEvent.keyDown(link, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  expect(document.querySelector("style")).toBeNull();
});

it("dismisses on outside pointer, focus departure and close button", () => {
  showShell();
  const trigger = screen.getByRole("button", { name: "Account menu for member" });
  fireEvent.click(trigger);
  fireEvent.pointerDown(screen.getByRole("heading", { name: "Preview" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.focusIn(screen.getByRole("link", { name: "Reports" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: "Close account menu" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  fireEvent.click(trigger);
  fireEvent.click(trigger);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it.each([
  [false, false, "expired", "Member", "Subscription expired"],
  [true, false, "staff", "Staff", "Subscription exempt"],
  [true, true, "staff", "Superuser", "Subscription exempt"],
  [false, false, "active", "Member", "Active subscription"],
  [false, false, "none", "Member", "No subscription"],
] as const)(
  "shows role and subscription for staff=%s superuser=%s state=%s",
  (is_staff, is_superuser, subscription_state, role, subscription) => {
    showShell({ ...session, is_staff, is_superuser, subscription_state, email: "" });
    fireEvent.click(screen.getByRole("button", { name: "Account menu for member" }));
    expect(screen.getByRole("dialog")).toHaveTextContent(role);
    expect(screen.getByRole("dialog")).toHaveTextContent(subscription);
    expect(screen.getByRole("dialog")).toHaveTextContent("Email not set");
  },
);

it("disables logout without CSRF and explains recovery", () => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  showShell();
  fireEvent.click(screen.getByRole("button", { name: "Account menu for member" }));
  expect(screen.getByRole("button", { name: "Log out" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("Reload the page to enable secure logout.");
});

it("closes account details when the route changes", () => {
  const view = showShell();
  fireEvent.click(screen.getByRole("button", { name: "Account menu for member" }));
  view.rerender(
    <ThemeProvider>
      <ApplicationShell session={session} pathname="/account/">
        <h1>Account</h1>
      </ApplicationShell>
    </ThemeProvider>,
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("keeps a dismissed market notice hidden when navigating into Ops", () => {
  const value = {
    ...session,
    is_staff: true,
    market_calendar: {
      ...session.market_calendar,
      is_open: false,
      status_key: "closed",
      reason: "Weekend",
    },
  };
  const view = showShell(value);
  fireEvent.click(screen.getByRole("button", { name: "Dismiss market notice" }));
  view.rerender(
    <ThemeProvider>
      <ApplicationShell session={value} pathname="/ops/jobs/">
        <h1>Jobs preview</h1>
      </ApplicationShell>
    </ThemeProvider>,
  );
  expect(screen.queryByRole("status", { name: "Market closed" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Trading calendar" })).toBeInTheDocument();
});
