import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zNewsPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const newsSearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  source: z.string().max(100).default(""),
  sentiment: z.enum(["", "positive", "negative", "neutral", "unscored"]).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  sort: z
    .string()
    .regex(/^(|-?(title|source|published_at|score|relevance))$/)
    .optional(),
  page_size: pageSizeSchema,
});
export type NewsSearch = z.infer<typeof newsSearchSchema>;

export function newsQuery(filters: NewsSearch) {
  return queryOptions({
    queryKey: ["app", "news", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({
        q: filters.q,
        source: filters.source,
        sentiment: filters.sentiment,
        page: String(filters.page),
      });
      tableParams(params, filters);
      const result = zNewsPage.safeParse(await appRequest(`/api/app/news?${params}`, { signal }));
      if (!result.success) {
        throw new ApiError(
          "contract",
          "The news response does not match this app. Reload the page.",
        );
      }
      return result.data;
    },
  });
}
