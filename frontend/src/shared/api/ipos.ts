import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zIpoDetail, zIpoPage } from "./generated/zod.gen";

export const ipoSearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  status: z.enum(["", "open", "upcoming", "closed", "listed", "all"]).default(""),
  verdict: z.enum(["", "good", "mixed", "weak", "unknown"]).default(""),
  category: z.enum(["", "mainboard", "sme"]).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
});
export type IpoSearch = z.infer<typeof ipoSearchSchema>;

export function iposQuery(filters: IpoSearch) {
  return queryOptions({
    queryKey: ["app", "ipos", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ ...filters, page: String(filters.page) });
      const result = zIpoPage.safeParse(await appRequest(`/api/app/ipos?${params}`, { signal }));
      if (!result.success)
        throw new ApiError(
          "contract",
          "The IPO list response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}

export function ipoQuery(id: string) {
  return queryOptions({
    queryKey: ["app", "ipo", id],
    queryFn: async ({ signal }) => {
      const result = zIpoDetail.safeParse(
        await appRequest(`/api/app/ipos/${encodeURIComponent(id)}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The IPO response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
