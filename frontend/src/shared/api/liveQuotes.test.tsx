import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { MockWebSocket } from "../../test/websocket";
import { liveSocketUrl, useLiveQuotes } from "./liveQuotes";

const nifty = {
  key: "NSE_INDEX|Nifty 50",
  kind: "index",
  name: "Nifty 50",
  company_id: null,
  ltp: 24500.5,
  as_of: "2026-10-26T04:30:00Z",
  previous_close: 24400,
  change: 100.5,
  change_pct: 0.41,
};
const example = {
  ...nifty,
  key: "NSE_EQ|INE000000001",
  kind: "equity",
  name: "Example Industries",
  symbol: "EXAMPLE",
  company_id: 7,
  ltp: 101.25,
  depth: [{ bid_price: 101.2, bid_qty: 10, ask_price: 101.3, ask_qty: 5 }],
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

it("builds a same-origin socket address", () => {
  expect(liveSocketUrl({ protocol: "https:", host: "kash.test" } as Location)).toBe(
    "wss://kash.test/ws/live/quotes/",
  );
  expect(liveSocketUrl({ protocol: "http:", host: "localhost:8000" } as Location)).toBe(
    "ws://localhost:8000/ws/live/quotes/",
  );
});

it("subscribes, merges snapshots and live quotes, and resubscribes on change", () => {
  const { result, rerender } = renderHook(({ ids }) => useLiveQuotes(ids), {
    initialProps: { ids: [7] },
  });
  const socket = MockWebSocket.latest;
  expect(result.current.connection).toBe("connecting");

  act(() => socket.open());
  expect(socket.sent).toEqual([{ type: "subscribe", companies: [7] }]);
  act(() =>
    socket.receive({
      type: "snapshot",
      quotes: [nifty, example, { key: "bad" }],
      status: { segments: { NSE_EQ: "NORMAL_OPEN" }, as_of: nifty.as_of },
    }),
  );
  expect(result.current.connection).toBe("live");
  expect(result.current.indices.map((quote) => quote.name)).toEqual(["Nifty 50"]);
  expect(result.current.companies.get(7)?.depth).toHaveLength(1);
  expect(result.current.status?.segments.NSE_EQ).toBe("NORMAL_OPEN");

  act(() => socket.receive({ type: "quotes", quotes: [{ ...nifty, ltp: 24510 }] }));
  expect(result.current.indices[0].ltp).toBe(24510);
  expect(result.current.companies.get(7)?.ltp).toBe(101.25);

  act(() => socket.receive({ type: "status", status: { segments: {}, as_of: nifty.as_of } }));
  expect(result.current.status?.segments).toEqual({});

  rerender({ ids: [9, 7, 7] });
  expect(socket.sent.at(-1)).toEqual({ type: "subscribe", companies: [7, 9] });
});

it("ignores malformed frames", () => {
  const { result } = renderHook(() => useLiveQuotes([]));
  const socket = MockWebSocket.latest;
  act(() => socket.open());
  act(() => socket.onmessage?.({ data: "not json" } as MessageEvent));
  act(() => socket.receive({ type: "unknown" }));
  expect(result.current.indices).toEqual([]);
});

it("reconnects with backoff and stops when access is refused", () => {
  const { result } = renderHook(() => useLiveQuotes([]));
  act(() => MockWebSocket.latest.serverClose(1006));
  expect(result.current.connection).toBe("reconnecting");
  expect(MockWebSocket.instances).toHaveLength(1);

  act(() => vi.advanceTimersByTime(1000));
  expect(MockWebSocket.instances).toHaveLength(2);
  act(() => MockWebSocket.latest.serverClose(1006));
  act(() => vi.advanceTimersByTime(1000));
  expect(MockWebSocket.instances).toHaveLength(2);
  act(() => vi.advanceTimersByTime(1000));
  expect(MockWebSocket.instances).toHaveLength(3);

  act(() => MockWebSocket.latest.serverClose(4403));
  expect(result.current.connection).toBe("unavailable");
  act(() => vi.advanceTimersByTime(60_000));
  expect(MockWebSocket.instances).toHaveLength(3);
});

it("reports a signed-out close and stays closed", () => {
  const { result } = renderHook(() => useLiveQuotes([]));
  act(() => MockWebSocket.latest.serverClose(4401));
  expect(result.current.connection).toBe("signed-out");
});

it("does not connect when disabled and closes on unmount", () => {
  const { result } = renderHook(() => useLiveQuotes([7], false));
  expect(result.current.connection).toBe("unavailable");
  expect(MockWebSocket.instances).toHaveLength(0);

  const { unmount } = renderHook(() => useLiveQuotes([]));
  const socket = MockWebSocket.latest;
  unmount();
  expect(socket.readyState).toBe(socket.CLOSED);
  act(() => vi.advanceTimersByTime(60_000));
  expect(MockWebSocket.instances).toHaveLength(1);
});
