import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { ApiError } from "../api/errors";
import { AppError, AppLoading } from "./AppStatus";

const { invalidate } = vi.hoisted(() => ({ invalidate: vi.fn().mockResolvedValue(undefined) }));
vi.mock("@tanstack/react-router", () => ({ useRouter: () => ({ invalidate }) }));

function showError(error: Error) {
  render(
    <ThemeProvider>
      <AppError error={error} reset={() => {}} />
    </ThemeProvider>,
  );
}

it("announces pending session loading", () => {
  render(
    <ThemeProvider>
      <AppLoading />
    </ThemeProvider>,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Loading your account...");
  expect(screen.getByRole("main")).toHaveAttribute("aria-busy", "true");
});

it("offers a retry for a server failure", () => {
  showError(new ApiError("server", "The server could not process the request."));
  expect(screen.getByRole("alert")).toHaveTextContent("The server could not process the request.");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(invalidate).toHaveBeenCalledOnce();
});

it("shows account access failures without retrying a permission denial", () => {
  showError(
    new ApiError("forbidden", "This feature is not available.", {
      code: "feature_not_available",
    }),
  );
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Not on your account");
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open your account" })).toHaveAttribute(
    "href",
    "/account/",
  );
});

it("provides a sign-in link when the session expires", () => {
  showError(new ApiError("unauthorized", "Sign in to continue."));
  expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute(
    "href",
    expect.stringContaining("/login/?next="),
  );
});
