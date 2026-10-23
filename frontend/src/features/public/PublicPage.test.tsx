import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { PublicPage, publicPageSchema } from "./PublicPage";

function show(values: Record<string, unknown> = {}) {
  const data = publicPageSchema.parse({
    page: "landing",
    authenticated: false,
    csrf: "public-csrf",
    ...values,
  });
  return render(
    <ThemeProvider>
      <PublicPage data={data} />
    </ThemeProvider>,
  );
}

it("renders the anonymous landing without any session API request", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  show();
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Less noise.More perspective.",
  );
  expect(screen.getAllByRole("article")).toHaveLength(9);
  expect(screen.getByRole("link", { name: /Explore your dashboard/ })).toHaveAttribute(
    "href",
    "/login/",
  );
  for (const path of ["news", "markets", "ipos", "companies", "reports", "delivery"]) {
    expect(screen.getByRole("link", { name: `Open ${path}` })).toHaveAttribute("href", `/${path}/`);
  }
  expect(screen.getByText("Illustrative preview")).toBeInTheDocument();
  expect(screen.getByText(/Not financial advice/)).toBeInTheDocument();
  expect(screen.getByRole("contentinfo")).toContainElement(
    screen.getByRole("navigation", { name: "Resources" }),
  );
  expect(screen.getByRole("link", { name: /Explore API docs/ })).toHaveAttribute("href", "/docs/");
  expect(fetch).not.toHaveBeenCalled();
});

it("links signed-in landing visitors directly to React", () => {
  show({ authenticated: true });
  expect(screen.getByRole("link", { name: "Open dashboard" })).toHaveAttribute(
    "href",
    "/dashboard/",
  );
  expect(screen.getByRole("link", { name: /Explore your dashboard/ })).toHaveAttribute(
    "href",
    "/dashboard/",
  );
});

it("uses native Django login with CSRF, safe next state and password autocomplete", () => {
  show({ page: "login", next: "/news/?q=banks" });
  const form = screen.getByRole("button", { name: "Log in" }).closest("form")!;
  expect(form).toHaveAttribute("method", "post");
  expect(form).toHaveAttribute("action", "/login/");
  expect(form.querySelector('[name="csrfmiddlewaretoken"]')).toHaveValue("public-csrf");
  expect(form.querySelector('[name="next"]')).toHaveValue("/news/?q=banks");
  expect(screen.getByLabelText("User name")).toHaveAttribute("autocomplete", "username");
  expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "current-password");
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
  fireEvent.submit(form);
  expect(within(form).getByRole("button")).toBeDisabled();
  expect(form).toHaveAttribute("aria-busy", "true");
});

it("shows an explicit login failure without retaining submitted passwords", () => {
  show({ page: "login", invalid: true, password: "must-not-appear" });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "The user name or the password is not correct",
  );
  expect(screen.getByLabelText("Password")).toHaveValue("");
  expect(document.body).not.toHaveTextContent("must-not-appear");
});

it("renders React signup posting to Django with CSRF, invite and required legal agreement", () => {
  show({ page: "signup", legal_version: "2026-10-23" });
  expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
  const form = screen.getByRole("button", { name: "Create account" }).closest("form")!;
  expect(form).toHaveAttribute("action", "/signup/");
  expect(form).toHaveAttribute("method", "post");
  expect(form.querySelector('[name="csrfmiddlewaretoken"]')).toHaveValue("public-csrf");
  expect(form.querySelector('[name="legal_version"]')).toHaveValue("2026-10-23");
  expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email");
  expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
  expect(screen.getByLabelText("Invite code")).toBeRequired();
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByRole("checkbox")).toBeRequired();
  expect(screen.getByRole("link", { name: "Terms of Use" })).toHaveAttribute(
    "href",
    "/legal/#terms",
  );
  expect(screen.getByRole("link", { name: "Privacy Notice" })).toHaveAttribute(
    "href",
    "/legal/#privacy",
  );
  fireEvent.submit(form);
  expect(screen.getByRole("button", { name: /Creating account/ })).toBeDisabled();
  expect(form).toHaveAttribute("aria-busy", "true");
});

it("shows signup field errors without retaining secrets and hides invites for open registration", () => {
  show({
    page: "signup",
    invite_required: false,
    values: { username: "member", email: "member@example.test" },
    errors: { password2: ["Passwords do not match."], agree_to_legal: ["You must agree."] },
  });
  expect(screen.queryByLabelText("Invite code")).not.toBeInTheDocument();
  expect(screen.getByLabelText("User name")).toHaveValue("member");
  expect(screen.getByLabelText("Email")).toHaveValue("member@example.test");
  expect(screen.getByLabelText("Password")).toHaveValue("");
  expect(screen.getByLabelText("Confirm password")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText("Passwords do not match.")).toHaveAttribute("role", "alert");
  expect(screen.getByText("You must agree.")).toHaveAttribute("role", "alert");
});

it.each([true, false])(
  "explains immediate login after signup when email sent is %s",
  (email_sent) => {
    show({ page: "signup-complete", email_sent, email: "member@example.test" });
    expect(screen.getByRole("heading", { name: "Your account is ready" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Log in to your account/ })).toHaveAttribute(
      "href",
      "/login/",
    );
    expect(screen.getByText(/All features stay locked/)).toBeInTheDocument();
    if (email_sent)
      expect(
        screen.getByText(/sent a verification link to member@example.test/),
      ).toBeInTheDocument();
    else expect(screen.getByRole("alert")).toHaveTextContent(/account was created/);
  },
);

it.each([null, 1, 30])(
  "explains real lockout wait %s without exposing login details",
  (minutes) => {
    show({ page: "lockout", minutes });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Too many tries");
    expect(
      screen.getByText(minutes ? new RegExp(`about ${minutes} minute`) : /Ask an admin to unlock/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the login" })).toHaveAttribute(
      "href",
      "/login/",
    );
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  },
);

it("escapes denied feature text and offers React account and dashboard links", () => {
  show({ page: "access", feature: "<script>unsafe</script>", authenticated: true });
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Not on your account");
  expect(screen.getByText(/<script>unsafe/)).toBeInTheDocument();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account/");
  expect(screen.getByRole("link", { name: "Back to Today" })).toHaveAttribute(
    "href",
    "/dashboard/",
  );
});

it("switches public themes without runtime style injection", () => {
  show();
  const toggle = screen.getByRole("button", { name: "Toggle color scheme" });
  fireEvent.click(toggle);
  expect(document.documentElement).toHaveAttribute("data-mantine-color-scheme", "dark");
  expect(document.querySelector("style")).toBeNull();
  fireEvent.click(toggle);
  expect(document.documentElement).toHaveAttribute("data-mantine-color-scheme", "light");
});
