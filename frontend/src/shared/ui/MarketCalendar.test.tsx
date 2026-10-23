import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { session } from "../../test/session";
import type { TradingCalendar } from "../api/generated/types.gen";
import { MarketCalendar } from "./MarketCalendar";
import { ApplicationAlerts } from "./ApplicationAlerts";
import { dismissNotification, notificationStore, notify } from "./notifications";
import { Notifications } from "./Notifications";

const calendar: TradingCalendar = {
  ...session.market_calendar,
  is_open: false,
  status_key: "holiday",
  reason: "Republic Day",
  days: [
    {
      day: "2026-01-26",
      kind: "holiday",
      reason: "Republic Day",
      opens_at: "",
      closes_at: "",
      source_url: "",
    },
    {
      day: "2026-11-08",
      kind: "special",
      reason: "Example Muhurat session",
      opens_at: "18:00",
      closes_at: "19:00",
      source_url: "https://www.nseindia.com/",
    },
  ],
};
const clients: QueryClient[] = [];

afterEach(() => {
  clients.forEach((client) => client.clear());
  clients.length = 0;
  act(() => notificationStore.getSnapshot().forEach((notice) => dismissNotification(notice.id)));
});

function show(value = calendar, canManage = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  clients.push(client);
  const content = (data: TradingCalendar) => (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MarketCalendar calendar={data} canManage={canManage} />
      </QueryClientProvider>
    </ThemeProvider>
  );
  return { ...render(content(value)), content };
}

it("shows a closeable Mantine closure alert without removing calendar access", () => {
  const view = show();
  expect(screen.getByRole("status")).toHaveClass("mantine-Alert-root");
  expect(screen.getByRole("status")).toHaveTextContent("Market closed");
  expect(screen.getByRole("status")).toHaveTextContent("Republic Day");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss market notice" }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Trading calendar" })).toBeInTheDocument();
  view.rerender(view.content({ ...calendar }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  view.rerender(view.content({ ...calendar, status_key: "weekend", reason: "Weekend" }));
  expect(screen.getByRole("status")).toHaveTextContent("Weekend");
});

it("lists holiday reasons, special session hours and sources in an accessible dialog", async () => {
  show(calendar, true);
  fireEvent.click(screen.getByRole("button", { name: "Trading calendar" }));
  expect(screen.getByRole("dialog", { name: "NSE trading calendar" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Republic Day" })).toBeInTheDocument();
  expect(
    screen.getByRole("cell", { name: /Special session 18:00 - 19:00 IST/ }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Exchange circular" })).toHaveAttribute(
    "href",
    "https://www.nseindia.com/",
  );
  expect(
    screen.getByRole("link", { name: "Manage holidays and special sessions" }),
  ).toHaveAttribute("href", "/admin/markets/tradingcalendarday/");
  expect(document.querySelector("style")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Close trading calendar" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("keeps the calendar available during normal sessions and hides staff management", () => {
  show(session.market_calendar);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Trading calendar" }));
  expect(screen.getByText(/does not mean there are no exchange holidays/)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Manage holidays/ })).not.toBeInTheDocument();
});

it("renders Mantine months with marked holidays and special sessions", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Trading calendar" }));
  const month = document.querySelector(".trading-calendar-month");
  expect(month).toBeInTheDocument();
  expect(month?.querySelector(".mantine-Calendar-month")).toBeInTheDocument();
  expect(month?.querySelector('[data-kind="holiday"]')).toHaveAttribute(
    "title",
    "Republic Day: Closed",
  );
  expect(screen.getByRole("button", { name: "Previous month" })).toBeDisabled();
  for (let count = 0; count < 10; count++) {
    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
  }
  expect(month?.querySelector('[data-kind="special"]')).toHaveAttribute(
    "title",
    "Example Muhurat session: 18:00 - 19:00 IST",
  );
  fireEvent.click(screen.getByRole("button", { name: "Next month" }));
  expect(screen.getByRole("button", { name: "Next month" })).toBeDisabled();
  expect(document.querySelector("style")).toBeNull();
});

it("announces open special sessions with their reason", () => {
  show({
    ...calendar,
    is_open: true,
    reason: "Example Muhurat session",
    special_reason: "Example Muhurat session",
  });
  expect(screen.getByRole("status")).toHaveTextContent("Special trading session");
  expect(screen.getByRole("status")).toHaveTextContent("Example Muhurat session");
});

it("browses years, surfaces request errors and supports retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ code: "unavailable", detail: "Calendar temporarily unavailable." }),
          { status: 503, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
  );
  show();
  fireEvent.click(screen.getByRole("button", { name: "Trading calendar" }));
  fireEvent.click(screen.getByRole("button", { name: "Next year" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Calendar temporarily unavailable.");
  expect(fetch).toHaveBeenCalledWith("/api/app/calendar?year=2027", expect.anything());
  vi.mocked(fetch).mockImplementation(
    async () =>
      new Response(
        JSON.stringify({
          ...calendar,
          year: 2027,
          days: [],
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByText(/No holidays or special sessions have been added for 2027/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Previous year" }));
  expect(screen.getByRole("cell", { name: "Republic Day" })).toBeInTheDocument();
});

it("shows persistent application warnings only once at the top and allows closing", () => {
  render(
    <ThemeProvider>
      <ApplicationAlerts />
      <Notifications />
    </ThemeProvider>,
  );
  act(() => {
    notify({
      id: "connection",
      title: "Connection lost",
      message: "Reconnecting.",
      tone: "warning",
      persistent: true,
    });
  });
  expect(screen.getAllByText("Reconnecting.")).toHaveLength(1);
  expect(screen.getByRole("status")).toHaveClass("mantine-Alert-root");
  fireEvent.click(screen.getByRole("button", { name: "Dismiss Connection lost" }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
