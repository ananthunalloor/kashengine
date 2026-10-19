import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zCompanyPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const companySearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  sector: z.string().max(100).optional(),
  sort: z
    .string()
    .regex(/^(|-?(name|symbol|sector|last_updated))$/)
    .optional(),
  page_size: pageSizeSchema,
});
export type CompanySearch = z.infer<typeof companySearchSchema>;

export function companiesQuery(filters: CompanySearch) {
  return queryOptions({
    queryKey: ["app", "companies", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: filters.q, page: String(filters.page) });
      tableParams(params, filters);
      if (filters.sector) params.set("sector", filters.sector);
      const result = zCompanyPage.safeParse(
        await appRequest(`/api/app/companies?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Companies response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
