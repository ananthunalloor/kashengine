import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import type { DeliveryPage } from "../../shared/api/generated/types.gen";
import { session } from "../../test/session";

const data: DeliveryPage = {
  chat_count: 2,
  items: [
    {
      id: 2,
      channel: "Email",
      status: "failed",
      status_label: "Failed",
      created_at: "2026-10-16T23:00:00Z",
      error: "<b>Plain diagnostic</b>",
      report_date: null,
    },
    {
      id: 1,
      channel: "Telegram",
      status: "sent",
      status_label: "Sent",
      created_at: "2026-10-16T03:00:00Z",
      error: null,
      report_date: "2026-10-16",
    },
  ],
};
const clients: QueryClient[] = [];
afterEach(() => {
  document.cookie = "csrftoken=; Max-Age=0; path=/";
  clients.forEach((client) => client.clear());
  clients.length = 0;
});

async function showDelivery({
  body = data,
  status = 200,
  staff = false,
  reports = true,
}: { body?: unknown; status?: number; staff?: boolean; reports?: boolean } = {}) {
  document.cookie = "csrftoken=delivery-test-csrf; path=/";
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string) => {
      const isSession = input === "/api/app/session";
      const report = input.startsWith("/api/app/reports/");
      return new Response(
        JSON.stringify(
          isSession
            ? {
                ...session,
                is_staff: staff,
                features: [
                  ...session.features.filter((key) => key !== "reports"),
                  "delivery",
                  ...(reports ? ["reports"] : []),
                ],
                navigation: [...session.navigation, { label: "Delivery", url: "/delivery/" }],
              }
            : report
              ? {
                  date: "2026-10-16",
                  prediction: "",
                  strength: null,
                  text: "Saved report",
                  deliveries: [],
                  older: null,
                  newer: null,
                }
              : body,
        ),
        {
          status: isSession || report ? 200 : status,
          headers: { "Content-Type": "application/json" },
        },
      );
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const router = createRouter({
    routeTree,
    basepath: "/app",
    trailingSlash: "always",
    history: createMemoryHistory({ initialEntries: ["/app/delivery/"] }),
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

it("shows configuration count, channels, test/report attempts and IST times", async () => {
  await showDelivery();
  expect(await screen.findByRole("heading", { level: 1, name: "Delivery" })).toHaveFocus();
  expect(document.title).toBe("Delivery | Kash Engine");
  expect(screen.getByText("The report goes to 2 Telegram chats.")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Email" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Telegram" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Failed" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Sent" })).toBeInTheDocument();
  expect(screen.getByText("Test")).toBeInTheDocument();
  expect(screen.getByText(/17 Oct 2026, 04:30 am IST/i)).toBeInTheDocument();
  expect(screen.queryByText("<b>Plain diagnostic</b>")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Compare with/ })).toHaveAttribute("href", "/delivery/");
  expect(screen.getByRole("link", { name: "Delivery", current: "page" })).toHaveAttribute(
    "href",
    "/app/delivery/",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(document.querySelector("style")).toBeNull();
});

it("navigates to the React report detail without leaving the app", async () => {
  const router = await showDelivery();
  const link = await screen.findByRole("link", { name: "16 Oct 2026" });
  expect(link).toHaveAttribute("href", "/app/reports/2026-10-16/");
  fireEvent.click(link);
  expect(await screen.findByText("Saved report")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/reports/2026-10-16/");
});

it("shows report dates without inaccessible links when Reports is blocked", async () => {
  await showDelivery({ reports: false });
  expect(await screen.findByText("16 Oct 2026")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "16 Oct 2026" })).not.toBeInTheDocument();
});

it("renders staff diagnostics as plain text", async () => {
  await showDelivery({ staff: true });
  expect(await screen.findByText("<b>Plain diagnostic</b>")).toBeInTheDocument();
  expect(document.querySelector(".report-diagnostic b")).toBeNull();
});

it.each([false, true])(
  "shows appropriate empty configuration guidance for staff=%s",
  async (staff) => {
    await showDelivery({ staff, body: { chat_count: 0, items: [] } });
    expect(await screen.findByText("Nothing was sent yet.")).toBeInTheDocument();
    if (staff) {
      expect(screen.getByRole("link", { name: "Ops > Settings > Telegram" })).toHaveAttribute(
        "href",
        "/ops/settings/telegram/",
      );
    } else {
      expect(screen.getByText("The daily report is not sent to Telegram yet.")).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /Ops/ })).not.toBeInTheDocument();
    }
  },
);

it("uses singular chat for one recipient", async () => {
  await showDelivery({ body: { ...data, chat_count: 1 } });
  expect(await screen.findByText("The report goes to 1 Telegram chat.")).toBeInTheDocument();
});

it.each([401, 403])("surfaces %s access failures inside the shell", async (status) => {
  await showDelivery({
    status,
    body: {
      code: status === 401 ? "unauthenticated" : "feature_not_available",
      detail: "Delivery unavailable.",
    },
  });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      status === 401 ? "Sign in to continue" : "Not on your account",
    ),
  );
  expect(screen.getByRole("link", { name: "Back to Delivery" })).toHaveAttribute(
    "href",
    "/app/delivery/",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("rejects contract drift and retries successfully", async () => {
  await showDelivery({ body: { items: [{}] } });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("does not match this app"),
  );
  vi.mocked(fetch).mockImplementation(
    async () =>
      new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("The report goes to 2 Telegram chats.")).toBeInTheDocument();
});
