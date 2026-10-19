import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zReportDetail, zReportPage } from "./generated/zod.gen";

export function reportsQuery(page: number) {
  return queryOptions({
    queryKey: ["app", "reports", { page }],
    queryFn: async ({ signal }) => {
      const result = zReportPage.safeParse(
        await appRequest(`/api/app/reports?page=${page}`, { signal }),
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
