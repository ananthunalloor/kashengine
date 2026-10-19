import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zReportDetail, zReportPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const reportSearchSchema = z.object({
  page: z.coerce.number().int().positive().safe().default(1),
  q: z.string().trim().max(100).optional(),
  direction: z.enum(["", "up", "down", "flat", "unknown"]).optional(),
  sort: z
    .string()
    .regex(/^(|-?(date|prediction|strength))$/)
    .optional(),
  page_size: pageSizeSchema,
});
export type ReportSearch = z.infer<typeof reportSearchSchema>;

export function reportsQuery(filters: ReportSearch) {
  return queryOptions({
    queryKey: ["app", "reports", filters],
    queryFn: async ({ signal }) => {
      const params = tableParams(new URLSearchParams({ page: String(filters.page) }), filters);
      if (filters.q) params.set("q", filters.q);
      if (filters.direction) params.set("direction", filters.direction);
      const result = zReportPage.safeParse(
        await appRequest(`/api/app/reports?${params}`, { signal }),
      );
      if (!result.success) {
        throw new ApiError(
          "contract",
          "The reports response does not match this app. Reload the page.",
        );
      }
      return result.data;
    },
  });
}

export function reportQuery(day: string) {
  return queryOptions({
    queryKey: ["app", "report", day],
    queryFn: async ({ signal }) => {
      const result = zReportDetail.safeParse(
        await appRequest(`/api/app/reports/${encodeURIComponent(day)}`, { signal }),
      );
      if (!result.success) {
        throw new ApiError(
          "contract",
          "The report response does not match this app. Reload the page.",
        );
      }
      return result.data;
    },
  });
}
