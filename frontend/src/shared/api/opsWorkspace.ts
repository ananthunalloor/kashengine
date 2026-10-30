import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest, csrfToken } from "./client";
import { ApiError } from "./errors";
import {
  zOpsActionResult,
  zOpsPage,
  zOpsForm,
  zOpsField,
  zOpsRow,
  zOpsTable,
} from "./generated/zod.gen";
import { pageSizeSchema } from "./tableSearch";

export const opsSearchSchema = z.object({
  q: z.string().max(200).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  page_size: pageSizeSchema,
  sort: z.string().max(100).default(""),
  state: z.string().max(100).default(""),
  role: z.string().max(100).default(""),
  active: z.string().max(100).default(""),
  kind: z.string().max(100).default(""),
  source: z.string().max(100).default(""),
  level: z.string().max(100).default(""),
  logger: z.string().max(100).default(""),
  hours: z.enum(["", "24", "168", "720"]).default(""),
  limit: z.coerce.number().int().min(1).max(1000).default(200),
  live: z.enum(["", "true"]).default(""),
});
export type OpsSearch = z.infer<typeof opsSearchSchema>;
export type OpsForm = z.infer<typeof zOpsForm>;
export type OpsField = z.infer<typeof zOpsField>;
export type OpsRow = z.infer<typeof zOpsRow>;
export type OpsTable = z.infer<typeof zOpsTable>;
export type OpsPage = z.infer<typeof zOpsPage>;
export type OpsActionResult = z.infer<typeof zOpsActionResult>;

export function opsPageQuery(path: string, filters: OpsSearch) {
  return queryOptions({
    queryKey: ["app", "ops", "page", path, filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.set(key, String(value));
      });
      const result = zOpsPage.safeParse(
        await appRequest(`/api/app/ops/pages/${path}?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Ops response does not match this app. Reload the page.",
        );
      return result.data;
    },
    retry: false,
  });
}

export async function submitOpsForm(form: { action: string; download?: boolean }, body: FormData) {
  if (!form.action.startsWith("/api/app/ops/actions/"))
    throw new ApiError("contract", "This Ops action is not supported.");
  const path: `/api/app/${string}` = `/api/app/${form.action.slice("/api/app/".length)}`;
  if (!form.download) {
    const result = zOpsActionResult.safeParse(await appRequest(path, { method: "POST", body }));
    if (!result.success)
      throw new ApiError(
        "contract",
        "The action returned an unexpected response. Check the audit trail before retrying.",
      );
    return result.data;
  }
  const token = csrfToken();
  if (!token) throw new ApiError("forbidden", "Reload the page to restore your security token.");
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      body,
      credentials: "same-origin",
      redirect: "error",
      headers: { "X-CSRFToken": token },
    });
  } catch {
    throw new ApiError("network", "The download did not complete. Check your connection.");
  }
  if (
    response.headers.get("Content-Type")?.includes("json") &&
    !response.headers.has("Content-Disposition")
  ) {
    const body: unknown = await response.json();
    const result = zOpsActionResult.safeParse(body);
    if (response.ok && result.success) return result.data;
    const problem = z.object({ detail: z.string() }).safeParse(body);
    throw new ApiError(
      response.status === 401 ? "unauthorized" : response.status === 403 ? "forbidden" : "server",
      problem.success ? problem.data.detail : "Snapshot download failed.",
    );
  }
  if (!response.ok || !response.headers.get("Content-Disposition")?.startsWith("attachment"))
    throw new ApiError("server", "Snapshot download failed. No file was saved.");
  const url = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download =
      response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] ??
      "kashengine-snapshot.json";
    document.body.append(anchor);
    try {
      anchor.click();
    } finally {
      anchor.remove();
    }
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return {
    ok: true,
    messages: [
      { level: "success", text: "Database snapshot download started. Store the file securely." },
    ],
    redirect: "",
    page: null,
  };
}
