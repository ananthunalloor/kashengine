import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
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
  return { ...view, client, invalidate, source: MockEventSource.current };
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
    source.emit("ready", { resync: true });
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
    source.emit("ready", { resync: false });
  });
  expect(notificationStore.getSnapshot()).toHaveLength(0);
});

it("does not fetch on idle ticks or routine authenticated stream renewals", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const { source, invalidate } = show();
  act(() => {
    source.emit("ready", { resync: true });
    vi.advanceTimersByTime(250);
  });
  invalidate.mockClear();
  act(() => {
    for (let renewal = 0; renewal < 3; renewal++) {
      source.emit("refresh", {});
      source.emit("reconnect", {});
      source.onerror?.();
      source.emit("ready", { resync: false });
      vi.advanceTimersByTime(20_000);
    }
  });
  expect(invalidate).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  expect(notificationStore.getSnapshot()).toHaveLength(0);
});

it("resynchronizes after a replay gap and after a genuine connection failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(session))),
  );
  const { source, invalidate } = show();
  act(() => {
    source.emit("ready", { resync: true });
    vi.advanceTimersByTime(250);
  });
  expect(invalidate).toHaveBeenCalledTimes(1);
  await act(async () => {
    source.emit("reconnect", {});
    source.onerror?.();
    source.onerror?.();
  });
  act(() => {
    source.emit("ready", { resync: false });
    vi.advanceTimersByTime(250);
  });
  expect(invalidate).toHaveBeenCalledTimes(2);
});

it("updates rendered status and table values only after a relevant change", async () => {
  const { client, source } = show();
  let saved = { status: "Waiting", value: 10 };
  const read = vi.fn(async () => saved);
  function StatusTable() {
    const { data } = useQuery({
      queryKey: ["app", "ops", "runs"],
      queryFn: read,
    });
    return (
      <table>
        <tbody>
          <tr>
            <td>{data?.status}</td>
            <td>{data?.value}</td>
          </tr>
        </tbody>
      </table>
    );
  }
  const table = render(
    <QueryClientProvider client={client}>
      <StatusTable />
    </QueryClientProvider>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(screen.getByRole("cell", { name: "Waiting" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "10" })).toBeInTheDocument();
  saved = { status: "Done", value: 25 };
  await act(async () => {
    source.emit("refresh", {});
    source.emit("change", { scope: "news" });
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(read).toHaveBeenCalledTimes(1);
  await act(async () => {
    source.emit("change", { scope: "ops" });
    await vi.advanceTimersByTimeAsync(300);
  });
  expect(read).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("cell", { name: "Done" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "25" })).toBeInTheDocument();
  table.unmount();
  client.clear();
});

it("refreshes changed scopes but respects paused, hidden, or errored live logs", () => {
  const { source, invalidate } = show();
  act(() => {
    source.emit("change", { scope: "ops" });
    vi.advanceTimersByTime(250);
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
  const liveKey = ["app", "ops", "page", "logs/", { live: "true" }];
  client.setQueryData(liveKey, { refresh_seconds: 5 });
  const liveQuery = client.getQueryCache().find({ queryKey: liveKey });
  expect(liveQuery && predicate?.(liveQuery)).toBe(true);
  if (liveQuery) {
    liveQuery.setState({ error: new Error("Unavailable") });
    expect(predicate?.(liveQuery)).toBe(false);
    liveQuery.setState({ error: null });
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    expect(predicate?.(liveQuery)).toBe(false);
    visibility.mockRestore();
  }
  client.setQueryData(["app", "news"], {});
  const news = client.getQueryCache().find({ queryKey: ["app", "news"] });
  expect(news && predicate?.(news)).toBe(false);
  client.clear();
});
