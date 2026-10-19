import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zCompanyPage } from "./generated/zod.gen";

export const companySearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
});
export type CompanySearch = z.infer<typeof companySearchSchema>;

export function companiesQuery(filters: CompanySearch) {
  return queryOptions({
    queryKey: ["app", "companies", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: filters.q, page: String(filters.page) });
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
