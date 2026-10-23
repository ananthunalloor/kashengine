import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { z } from "zod";

import { loginUrl } from "../api/client";
import { ApiError } from "../api/errors";
import { sessionQuery } from "../api/session";
import { dismissNotification, notify, notifyError } from "./notifications";

const changeSchema = z.object({
  scope: z.enum([
    "news",
    "companies",
    "markets",
    "ipos",
    "reports",
    "delivery",
    "ops",
    "account",
    "session",
    "all",
  ]),
  run: z
    .object({
      id: z.number().int().positive(),
      label: z.string(),
      status: z.enum(["pending", "started", "success", "failure"]),
    })
    .optional(),
});

const related: Record<z.infer<typeof changeSchema>["scope"], string[]> = {
  news: ["news", "today"],
  companies: ["companies", "news", "today"],
  markets: ["markets", "today"],
  ipos: ["ipos", "ipo", "today"],
  reports: ["reports", "report", "today"],
  delivery: ["delivery", "reports", "report", "today"],
  ops: ["ops"],
  account: ["account", "session"],
  session: ["session", "account", "ops"],
  all: [
    "news",
    "companies",
    "markets",
    "ipos",
    "ipo",
    "reports",
    "report",
    "delivery",
    "today",
    "ops",
    "account",
    "session",
  ],
};

export function LiveUpdates({ staff }: { staff: boolean }) {
  const client = useQueryClient();
  useEffect(() => {
    if (typeof EventSource === "undefined") {
      notify({
        id: "live-unavailable",
        title: "Live updates unavailable",
        message: "Your browser does not support live updates. Refresh manually to see changes.",
        tone: "warning",
        persistent: true,
      });
      return;
    }
    const source = new EventSource(staff ? "/api/app/ops/events" : "/api/app/events");
    let timer: number | undefined;
    let connectionTimer: number | undefined;
    let checking = false;
    let disposed = false;
    let renewing = false;
    let needsResync = false;
    const scopes = new Set<string>();
    const seen = new Set<string>();
    function refresh(keys: string[]) {
      keys.forEach((key) => scopes.add(key));
      if (timer !== undefined) return;
      timer = window.setTimeout(() => {
        timer = undefined;
        const pending = new Set(scopes);
        scopes.clear();
        void client.invalidateQueries({
          predicate: (query) =>
            query.queryKey[0] === "app" &&
            pending.has(String(query.queryKey[1])) &&
            !(
              query.queryKey[1] === "ops" &&
              query.queryKey[2] === "page" &&
              query.queryKey[3] === "logs/" &&
              (document.visibilityState === "hidden" ||
                query.state.error ||
                !query.state.data ||
                typeof query.state.data !== "object" ||
                !("refresh_seconds" in query.state.data) ||
                !query.state.data.refresh_seconds)
            ),
        });
      }, 250);
    }
    source.addEventListener("ready", (event) => {
      window.clearTimeout(connectionTimer);
      connectionTimer = undefined;
      dismissNotification("live-connection");
      renewing = false;
      let data: unknown;
      try {
        data = JSON.parse(event.data);
      } catch {
        notifyError(
          new Error("Live updates returned unreadable data. Reload the page."),
          "Live update failed",
        );
        return;
      }
      const ready = z.object({ resync: z.boolean() }).safeParse(data);
      if (!ready.success) {
        notifyError(
          new Error("Live updates do not match this app. Reload the page."),
          "Live update failed",
        );
        return;
      }
      if (ready.data.resync || needsResync) refresh(Object.values(related).flat());
      needsResync = false;
    });
    source.addEventListener("reconnect", () => {
      renewing = true;
    });
    source.addEventListener("change", (event) => {
      let data: unknown;
      try {
        data = JSON.parse(event.data);
      } catch {
        notifyError(
          new Error("Live updates returned unreadable data. Reload the page."),
          "Live update failed",
        );
        return;
      }
      const change = changeSchema.safeParse(data);
      if (!change.success) {
        notifyError(
          new Error("Live updates do not match this app. Reload the page."),
          "Live update failed",
        );
        return;
      }
      const { scope, run } = change.data;
      refresh(related[scope]);
      if (!staff || !run) return;
      if (run.status === "success" || run.status === "failure") {
        // Completed jobs can use bulk writes, which do not emit model signals.
        refresh(Object.values(related).flat());
        const key = `${run.id}-${run.status}`;
        if (seen.has(key)) return;
        seen.add(key);
        if (seen.size > 1000) {
          const oldest = seen.values().next().value;
          if (oldest !== undefined) seen.delete(oldest);
        }
        notify({
          id: `run-${key}`,
          title: run.status === "success" ? "Job completed" : "Job failed",
          message:
            run.status === "success"
              ? `${run.label} finished successfully.`
              : `${run.label} failed. Open the task run for details.`,
          tone: run.status === "success" ? "success" : "error",
          persistent: run.status === "failure",
          href: `/ops/runs/${run.id}/`,
        });
      }
    });
    source.onerror = () => {
      if (renewing) {
        renewing = false;
        return;
      }
      needsResync = true;
      if (connectionTimer === undefined) {
        connectionTimer = window.setTimeout(() => {
          notify({
            id: "live-connection",
            title: "Live updates disconnected",
            message: "Reconnecting automatically. You can still refresh this page manually.",
            tone: "warning",
            persistent: true,
          });
        }, 5000);
      }
      if (checking) return;
      checking = true;
      void client
        .fetchQuery({ ...sessionQuery, staleTime: 0, retry: false })
        .catch((error: unknown) => {
          if (disposed) return;
          if (error instanceof ApiError && error.kind === "unauthorized") {
            source.close();
            window.location.assign(loginUrl());
          } else if (error instanceof ApiError && error.kind === "forbidden") {
            source.close();
            notifyError(error, "Live updates unavailable");
          } else {
            notifyError(error, "Live connection failed");
          }
        })
        .finally(() => {
          checking = false;
        });
    };
    return () => {
      disposed = true;
      source.close();
      window.clearTimeout(timer);
      window.clearTimeout(connectionTimer);
      dismissNotification("live-connection");
    };
  }, [client, staff]);
  return null;
}
