import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zCompanyPrice } from "./generated/zod.gen";

const zWatchlistAlert = z.object({
  id: z.number().int().positive(),
  above_price: z.coerce.number().positive(),
  is_active: z.boolean(),
  created_at: z.iso.datetime(),
  triggered_at: z.iso.datetime().nullable(),
  triggered_price: z.number().nullable(),
});

const zWatchlistItem = z.object({
  id: z.number().int().positive(),
  company: z.object({
    id: z.number().int().positive(),
    name: z.string(),
    symbol: z.string(),
    sector: z.string(),
  }),
  quote: zCompanyPrice.nullable(),
  alerts: z.array(zWatchlistAlert),
});

export const zWatchlistPage = z.object({ items: z.array(zWatchlistItem) });
export type WatchlistPage = z.infer<typeof zWatchlistPage>;
export type WatchlistItem = z.infer<typeof zWatchlistItem>;
export type WatchlistAlert = z.infer<typeof zWatchlistAlert>;

const zWatchlistNotification = z.object({
  id: z.number().int().positive(),
  company_id: z.number().int().positive(),
  company_name: z.string(),
  symbol: z.string(),
  above_price: z.coerce.number().positive(),
  triggered_price: z.number(),
  triggered_at: z.iso.datetime(),
});

const zWatchlistNotifications = z.array(zWatchlistNotification);
export type WatchlistNotification = z.infer<typeof zWatchlistNotification>;

async function parse<T>(body: unknown, schema: z.ZodType<T>, message: string): Promise<T> {
  const result = schema.safeParse(body);
  if (!result.success) throw new ApiError("contract", message);
  return result.data;
}

export function watchlistQuery() {
  return queryOptions({
    queryKey: ["app", "watchlist"],
    refetchInterval: 15_000,
    queryFn: async ({ signal }) =>
      parse(
        await appRequest("/api/app/watchlist", { signal }),
        zWatchlistPage,
        "The watchlist response does not match this app. Reload the page.",
      ),
  });
}

export async function addWatchlistCompany(companyId: number) {
  return parse(
    await appRequest(`/api/app/watchlist/${companyId}`, { method: "PUT" }),
    z.object({ watchlisted: z.literal(true) }),
    "The bookmark response does not match this app. Reload the page.",
  );
}

export async function removeWatchlistCompany(companyId: number) {
  return parse(
    await appRequest(`/api/app/watchlist/${companyId}`, { method: "DELETE" }),
    z.object({ watchlisted: z.literal(false) }),
    "The bookmark response does not match this app. Reload the page.",
  );
}

export async function createWatchlistPriceAlert(companyId: number, abovePrice: string) {
  return parse(
    await appRequest(`/api/app/watchlist/${companyId}/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ above_price: abovePrice }),
    }),
    zWatchlistAlert,
    "The price alert response does not match this app. Reload the page.",
  );
}

export async function deleteWatchlistPriceAlert(alertId: number) {
  return parse(
    await appRequest(`/api/app/watchlist/alerts/${alertId}`, { method: "DELETE" }),
    z.object({ ok: z.literal(true) }),
    "The price alert response does not match this app. Reload the page.",
  );
}

export function watchlistNotificationsQuery() {
  return queryOptions({
    queryKey: ["app", "watchlist-notifications"],
    refetchInterval: 15_000,
    queryFn: async ({ signal }) =>
      parse(
        await appRequest("/api/app/watchlist/notifications", { signal }),
        zWatchlistNotifications,
        "The price notification response does not match this app. Reload the page.",
      ),
  });
}

export async function markWatchlistNotificationRead(alertId: number) {
  return parse(
    await appRequest(`/api/app/watchlist/notifications/${alertId}/read`, { method: "POST" }),
    z.object({ ok: z.literal(true) }),
    "The price notification response does not match this app. Reload the page.",
  );
}
