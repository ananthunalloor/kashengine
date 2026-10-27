import { useEffect, useRef, useState } from "react";
import { z } from "zod";

const number = z.number().finite();
const depthSchema = z.object({
  bid_price: number.nullable(),
  bid_qty: number,
  ask_price: number.nullable(),
  ask_qty: number,
});

export const liveQuoteSchema = z.object({
  key: z.string(),
  kind: z.enum(["equity", "index"]),
  name: z.string().default(""),
  symbol: z.string().default(""),
  company_id: z.number().int().positive().nullable().default(null),
  ltp: number.positive(),
  as_of: z.string(),
  previous_close: number.nullable().default(null),
  change: number.nullable().default(null),
  change_pct: number.nullable().default(null),
  open: number.nullable().default(null),
  high: number.nullable().default(null),
  low: number.nullable().default(null),
  volume: number.nullable().default(null),
  average_price: number.nullable().default(null),
  total_buy_qty: number.nullable().default(null),
  total_sell_qty: number.nullable().default(null),
  depth: z.array(depthSchema).default([]),
});

export const marketStatusSchema = z.object({
  segments: z.record(z.string(), z.string()),
  as_of: z.string(),
});

const messageSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("snapshot"),
    quotes: z.array(z.unknown()),
    status: z.unknown().optional(),
  }),
  z.object({ type: z.literal("quotes"), quotes: z.array(z.unknown()) }),
  z.object({ type: z.literal("status"), status: z.unknown() }),
  z.object({ type: z.literal("error"), detail: z.string() }),
]);

export type LiveQuote = z.infer<typeof liveQuoteSchema>;
export type MarketStatus = z.infer<typeof marketStatusSchema>;
export type LiveConnection =
  | "connecting"
  | "live"
  | "reconnecting"
  | "signed-out"
  | "unavailable"
  | "unsupported";

export interface LiveMarket {
  connection: LiveConnection;
  indices: LiveQuote[];
  companies: Map<number, LiveQuote>;
  status: MarketStatus | null;
}

/** Close codes sent by the server consumer (apps/markets/consumers.py). */
const UNAUTHENTICATED = 4401;
const FORBIDDEN = 4403;
const MAX_BACKOFF_MS = 30_000;

export function liveSocketUrl(location: Location = window.location) {
  return `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/live/quotes/`;
}

function parseQuotes(items: unknown[]) {
  return items.flatMap((item) => {
    const quote = liveQuoteSchema.safeParse(item);
    return quote.success ? [quote.data] : [];
  });
}

/**
 * Follow live Upstox quotes relayed by the server WebSocket: all streamed indices and the
 * market status, plus up to 25 companies. The browser never talks to Upstox directly.
 */
export function useLiveQuotes(companies: number[], enabled = true): LiveMarket {
  const [state, setState] = useState<LiveMarket>(() => ({
    connection: enabled ? "connecting" : "unavailable",
    indices: [],
    companies: new Map(),
    status: null,
  }));
  const socketRef = useRef<WebSocket | null>(null);
  const subscription = [...new Set(companies)].sort((a, b) => a - b).join(",");
  const subscriptionRef = useRef(subscription);
  subscriptionRef.current = subscription;

  useEffect(() => {
    if (!enabled) {
      setState((previous) => ({ ...previous, connection: "unavailable" }));
      return;
    }
    if (typeof WebSocket === "undefined") {
      setState((previous) => ({ ...previous, connection: "unsupported" }));
      return;
    }
    let disposed = false;
    let attempt = 0;
    let timer: number | undefined;

    function merge(quotes: LiveQuote[], status?: MarketStatus | null) {
      setState((previous) => {
        const indices = new Map(previous.indices.map((quote) => [quote.key, quote]));
        const byCompany = new Map(previous.companies);
        for (const quote of quotes) {
          if (quote.company_id !== null) byCompany.set(quote.company_id, quote);
          else indices.set(quote.key, quote);
        }
        return {
          ...previous,
          connection: "live",
          indices: [...indices.values()],
          companies: byCompany,
          status: status === undefined ? previous.status : status,
        };
      });
    }

    function open() {
      const socket = new WebSocket(liveSocketUrl());
      socketRef.current = socket;
      socket.onopen = () => {
        attempt = 0;
        setState((previous) => ({ ...previous, connection: "live" }));
        const ids = subscriptionRef.current;
        socket.send(
          JSON.stringify({ type: "subscribe", companies: ids ? ids.split(",").map(Number) : [] }),
        );
      };
      socket.onmessage = (event) => {
        let data: unknown;
        try {
          data = JSON.parse(String(event.data));
        } catch {
          return;
        }
        const message = messageSchema.safeParse(data);
        if (!message.success) return;
        const value = message.data;
        if (value.type === "snapshot" || value.type === "quotes") {
          const status =
            value.type === "snapshot" && value.status !== undefined
              ? (marketStatusSchema.safeParse(value.status).data ?? null)
              : undefined;
          merge(parseQuotes(value.quotes), status);
        } else if (value.type === "status") {
          const status = marketStatusSchema.safeParse(value.status);
          if (status.success) merge([], status.data);
        }
      };
      socket.onclose = (event) => {
        if (socketRef.current === socket) socketRef.current = null;
        if (disposed) return;
        if (event.code === UNAUTHENTICATED || event.code === FORBIDDEN) {
          setState((previous) => ({
            ...previous,
            connection: event.code === UNAUTHENTICATED ? "signed-out" : "unavailable",
          }));
          return;
        }
        setState((previous) => ({ ...previous, connection: "reconnecting" }));
        const delay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS);
        attempt += 1;
        timer = window.setTimeout(open, delay);
      };
    }

    open();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [enabled]);

  useEffect(() => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== socket.OPEN) return;
    socket.send(
      JSON.stringify({
        type: "subscribe",
        companies: subscription ? subscription.split(",").map(Number) : [],
      }),
    );
  }, [subscription]);

  return state;
}
