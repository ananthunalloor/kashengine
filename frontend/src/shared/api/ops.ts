import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zOpsAuditPage, zOpsRunDetail, zOpsRunPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const runSearchSchema = z.object({
  q: z.string().trim().max(200).default(""),
  label: z.string().max(200).default(""),
  status: z.enum(["", "pending", "started", "success", "failure"]).default(""),
  trigger: z.enum(["", "auto", "manual"]).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  page_size: pageSizeSchema,
  sort: z
    .string()
    .regex(/^(|-?(label|started_at|duration_ms|trigger|status))$/)
    .optional(),
});
export type RunSearch = z.infer<typeof runSearchSchema>;

export const auditSearchSchema = z.object({
  q: z.string().trim().max(200).default(""),
  actor: z.string().max(150).default(""),
  action: z.string().max(50).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  page_size: pageSizeSchema,
  sort: z
    .string()
    .regex(/^(|-?(created_at|actor_name|action|target|ip_address))$/)
    .optional(),
});
export type AuditSearch = z.infer<typeof auditSearchSchema>;

export function auditQuery(filters: AuditSearch) {
  return queryOptions({
    queryKey: ["app", "ops", "audit", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ page: String(filters.page) });
      for (const key of ["q", "actor", "action"] as const) {
        if (filters[key]) params.set(key, filters[key]);
      }
      tableParams(params, filters);
      const result = zOpsAuditPage.safeParse(
        await appRequest(`/api/app/ops/audit?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The audit trail response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}

export function runsQuery(filters: RunSearch) {
  return queryOptions({
    queryKey: ["app", "ops", "runs", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ page: String(filters.page) });
      for (const key of ["q", "label", "status", "trigger"] as const) {
        if (filters[key]) params.set(key, filters[key]);
      }
      tableParams(params, filters);
      const result = zOpsRunPage.safeParse(
        await appRequest(`/api/app/ops/runs?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The task history response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}

export function runQuery(id: string) {
  return queryOptions({
    queryKey: ["app", "ops", "run", id],
    queryFn: async ({ signal }) => {
      const result = zOpsRunDetail.safeParse(
        await appRequest(`/api/app/ops/runs/${encodeURIComponent(id)}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The task run response does not match this app. Reload the page.",
        );
      return result.data;
    },
    retry: false,
    refetchInterval: (query) =>
      query.state.error ? false : query.state.data?.is_active ? 3000 : false,
  });
}

export async function stopRun(id: string) {
  const result = await appRequest(`/api/app/ops/runs/${encodeURIComponent(id)}/stop`, {
    method: "POST",
  });
  if (!result || typeof result !== "object") throw new ApiError("contract", "Stop request failed.");
  return result as { ok: boolean; status?: string };
}
