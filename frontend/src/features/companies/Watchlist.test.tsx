import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import { session } from "../../test/session";

const clients: QueryClient[] = [];

afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showWatchlist() {
  document.cookie = "csrftoken=watchlist-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  const saved = {
    items: [
      {
        id: 8,
        company: { id: 4, name: "Example Ltd", symbol: "EXAMPLE", sector: "Technology" },
        quote: {
          price: 110,
          previous_close: 100,
          change_pct: 10,
          volume: 300,
          mode: "stream",
          as_of: "2026-10-22T10:00:00Z",
          received_at: "2026-10-22T10:00:01Z",
        },
        alerts: [
          {
            id: 12,
            above_price: 105,
            is_active: false,
            created_at: "2026-10-22T09:00:00Z",
            triggered_at: "2026-10-22T10:00:00Z",
            triggered_price: 110,
          },
        ],
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      if (input === "/api/app/session") {
        return new Response(
          JSON.stringify({
            ...session,
            features: [...session.features, "companies", "markets"],
            navigation: [
              ...session.navigation,
              { label: "Companies", url: "/companies/" },
              { label: "Watchlist", url: "/watchlist/" },
            ],
          }),
          { headers: { "Content-Type": "application/json" } },
        );
      }
      if (input === "/api/app/watchlist/notifications") {
        return new Response("[]", { headers: { "Content-Type": "application/json" } });
      }
      if (input === "/api/app/watchlist" && init?.method !== "DELETE") {
        return new Response(JSON.stringify(saved), {
          headers: { "Content-Type": "application/json" },
        });
      }
      if (input === "/api/app/watchlist/4" && init?.method === "DELETE") {
        saved.items = [];
        return new Response(JSON.stringify({ watchlisted: false }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ detail: "Not found", code: "not_found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/",
    trailingSlash: "always",
    history: createMemoryHistory({ initialEntries: ["/watchlist/"] }),
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
}

it("shows saved quotes and triggered alerts, and removes a bookmark", async () => {
  await showWatchlist();

  expect(await screen.findByRole("heading", { name: "Watchlist" })).toBeInTheDocument();
  expect(screen.getByText("INR 110.00")).toBeInTheDocument();
  expect(screen.getByText("Price rises above INR 105.00 - alert sent")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Remove Example Ltd from watchlist" }));
  expect(await screen.findByText("Your watchlist is empty")).toBeInTheDocument();
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/app/watchlist/4",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
});
