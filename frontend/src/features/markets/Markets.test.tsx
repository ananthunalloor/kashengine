import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { Markets } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const data: Markets = {
  stats: {
    total: 2,
    correct: 1,
    accuracy: "50%",
    baseline_direction: "up",
    baseline_accuracy: "50%",
    high_confidence: { n: 1, correct: 1 },
    recent: { n: 2, correct: 1 },
    pending: 1,
    enough_results: false,
  },
  quotes: [{ name: "<b>Nifty 50</b>", day: "2026-10-16", close: "24500.00", change: "0.00%" }],
  history: [
    {
      date: "2026-10-16",
      direction: "up",
      strength: "6.4/10",
      actual_direction: "up",
      change: "+1.25%",
      result: "Right",
    },
    {
      date: "2026-10-15",
      direction: "down",
      strength: "1.0/10",
      actual_direction: "flat",
      change: "0.00%",
      result: "Wrong",
    },
    {
      date: "2026-10-14",
      direction: "flat",
      strength: "1.0/10",
      actual_direction: "",
      change: "-",
      result: "No session",
    },
    {
      date: "2026-10-13",
      direction: "up",
      strength: "1.0/10",
      actual_direction: "",
      change: "-",
      result: "Waiting",
    },
  ],
};
const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showMarkets({
  body = data,
  status = 200,
  staff = false,
}: { body?: unknown; status?: number; staff?: boolean } = {}) {
  document.cookie = "csrftoken=markets-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const isSession = input === "/api/app/session";
      return new Response(
        JSON.stringify(
          isSession
            ? {
                ...session,
                is_staff: staff,
                features: [...session.features, "markets"],
                navigation: [...session.navigation, { label: "Markets", url: "/markets/" }],
              }
            : body,
        ),
        { status: isSession ? 200 : status, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/",
    trailingSlash: "always",
    history: createMemoryHistory({ initialEntries: ["/markets/"] }),
    context: { queryClient: client },
    defaultPendingMinMs: 0,
  });
  await router.load();
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return router;
}

it("shows saved track record, baseline, sample warning, closes and all result states", async () => {
  await showMarkets();
  expect(await screen.findByRole("heading", { level: 1, name: "Markets" })).not.toHaveAttribute(
    "tabindex",
  );
  expect(document.title).toBe("Markets | Kash Engine");
  expect(screen.getByText(/right on 1 of 2 days \(50%\)/)).toHaveTextContent(
    "most common result (up)",
  );
  expect(screen.getByText(/too few results/)).toBeInTheDocument();
  expect(screen.getByText("1 of 1 right")).toBeInTheDocument();
  expect(screen.getByText("24500.00")).toBeInTheDocument();
  for (const state of ["Right", "Wrong", "No session", "Waiting"])
    expect(screen.getByRole("cell", { name: state })).toBeInTheDocument();
  expect(screen.getByText("6.4/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("+1.25%")).toHaveAttribute("data-tone", "positive");
  expect(screen.getAllByText("0.00%").every((node) => node.dataset.tone === "neutral")).toBe(true);
  expect(screen.getAllByText("1.0/10").every((node) => node.dataset.tone === "caution")).toBe(true);
  expect(screen.getByText(/not a probability/)).toBeInTheDocument();
  expect(screen.getAllByText("16 Oct 2026")).toHaveLength(2);
  expect(screen.getByRole("cell", { name: "<b>Nifty 50</b>" })).toBeInTheDocument();
  expect(document.querySelector(".data-table b")).toBeNull();
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/markets/");
  expect(screen.getByRole("link", { name: "Markets", current: "page" })).toHaveAttribute(
    "href",
    "/markets/",
  );
  expect(document.querySelector("style")).toBeNull();
});

it("colors a loss red while keeping a strong down prediction green", async () => {
  await showMarkets({
    body: {
      ...data,
      quotes: [{ ...data.quotes[0], change: "\u22121.25%" }],
      history: [{ ...data.history[0], direction: "down", strength: "9.1/10", change: "-1.50%" }],
    },
  });
  expect(await screen.findByText("\u22121.25%")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("-1.50%")).toHaveAttribute("data-tone", "negative");
  expect(screen.getByText("9.1/10")).toHaveAttribute("data-tone", "positive");
  expect(screen.getByText("Down")).toHaveAttribute("data-tone", "down");
});

it("shows missing data without suggesting zero accuracy and hides staff actions", async () => {
  await showMarkets({
    body: { ...data, quotes: [], history: [], stats: { ...data.stats, total: 0, pending: 1 } },
  });
  expect(await screen.findByText(/There are no results yet/)).toHaveTextContent(
    "1 waits for a result",
  );
  expect(screen.getByText("No saved closes yet.")).toBeInTheDocument();
  expect(screen.getByText("No prediction yet.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Jobs" })).not.toBeInTheDocument();
});

it("offers staff the existing Jobs action and omits warning for sufficient results", async () => {
  await showMarkets({
    staff: true,
    body: { ...data, history: [], stats: { ...data.stats, enough_results: true } },
  });
  expect(await screen.findByRole("link", { name: "Jobs" })).toHaveAttribute("href", "/ops/jobs/");
  expect(screen.queryByText(/too few results/)).not.toBeInTheDocument();
});

it.each([401, 403])("handles %s access errors inside the shell", async (status) => {
  await showMarkets({
    status,
    body: {
      code: status === 401 ? "unauthenticated" : "feature_not_available",
      detail: "Markets unavailable.",
    },
  });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      status === 401 ? "Sign in to continue" : "Not on your account",
    ),
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "Back to Markets" })).toHaveAttribute(
    "href",
    "/markets/",
  );
});

it("surfaces malformed contracts and retries a failed request", async () => {
  await showMarkets({ body: { stats: {} } });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("does not match this app"),
  );
  vi.mocked(fetch).mockImplementation(
    async () =>
      new Response(JSON.stringify(data), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Track record" })).toBeInTheDocument();
});
