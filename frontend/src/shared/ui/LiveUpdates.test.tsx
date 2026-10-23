import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { LiveUpdates } from "./LiveUpdates";
import { dismissNotification, notificationStore } from "./notifications";
import { session } from "../../test/session";

class MockEventSource {
  static current: MockEventSource;
  handlers = new Map<string, (event: MessageEvent) => void>();
  close = vi.fn();
  onerror: (() => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    MockEventSource.current = this;
  }
  addEventListener(name: string, handler: (event: MessageEvent) => void) {
    this.handlers.set(name, handler);
  }
  emit(name: string, payload: unknown) {
    this.handlers.get(name)?.(new MessageEvent(name, { data: JSON.stringify(payload) }));
  }
}

afterEach(() => {
  notificationStore.getSnapshot().forEach((notice) => dismissNotification(notice.id));
  vi.useRealTimers();
});

function show(staff = true) {
  vi.useFakeTimers();
  vi.stubGlobal("EventSource", MockEventSource);
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const view = render(
    <QueryClientProvider client={client}>
      <LiveUpdates staff={staff} />
    </QueryClientProvider>,
  );
  return { ...view, invalidate, source: MockEventSource.current };
}

it("subscribes once, coalesces changes, notifies completion once, and cleans up", () => {
  const { source, invalidate, unmount } = show();
  expect(source.url).toBe("/api/app/ops/events");
  const payload = { scope: "ops", run: { id: 42, label: "News fetch", status: "success" } };
  act(() => {
    source.emit("change", payload);
    source.emit("change", payload);
    vi.advanceTimersByTime(250);
  });
  expect(invalidate).toHaveBeenCalledTimes(1);
  expect(notificationStore.getSnapshot()).toHaveLength(1);
  expect(notificationStore.getSnapshot()[0]).toMatchObject({
    title: "Job completed",
    href: "/ops/runs/42/",
    tone: "success",
  });
  unmount();
  expect(source.close).toHaveBeenCalledOnce();
});

it("subscribes members to the non-staff stream and never displays job details", () => {
  const { source } = show(false);
  expect(source.url).toBe("/api/app/events");
  act(() => {
    source.emit("change", { scope: "ops", run: { id: 42, label: "Private", status: "failure" } });
  });
  expect(notificationStore.getSnapshot()).toHaveLength(0);
});

it("keeps job failures visible, rejects malformed events, and refreshes on reconnect", () => {
  const { source, invalidate } = show();
  act(() => {
    source.emit("change", { scope: "ops", run: { id: 9, label: "Backup", status: "failure" } });
    source.emit("change", { scope: "invalid" });
    source.emit("ready", {});
    vi.advanceTimersByTime(250);
  });
  expect(notificationStore.getSnapshot()).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ title: "Job failed", persistent: true }),
      expect.objectContaining({ title: "Live update failed", tone: "error" }),
    ]),
  );
  expect(invalidate).toHaveBeenCalledTimes(1);
});

it("shows connection loss after a delay and clears it when the stream recovers", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(session), {
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
  const { source } = show();
  await act(async () => {
    source.onerror?.();
  });
  expect(notificationStore.getSnapshot()).toHaveLength(0);
  act(() => {
    vi.advanceTimersByTime(5000);
  });
  expect(notificationStore.getSnapshot()).toEqual([
    expect.objectContaining({ id: "live-connection", tone: "warning" }),
  ]);
  act(() => {
    source.emit("ready", {});
  });
  expect(notificationStore.getSnapshot()).toHaveLength(0);
});

it("uses SSE ticks only for enabled runtime pages, not paused logs or errored pages", () => {
  const { source, invalidate } = show();
  act(() => {
    source.emit("refresh", {});
  });
  const predicate = invalidate.mock.calls[0][0]?.predicate;
  const client = new QueryClient();
  for (const [path, seconds] of [
    ["", 5],
    ["logs/", 0],
  ] as const) {
    const key = ["app", "ops", "page", path];
    client.setQueryData(key, { refresh_seconds: seconds });
    const query = client.getQueryCache().find({ queryKey: key });
    expect(query && predicate?.(query)).toBe(seconds > 0);
  }
  client.clear();
});
