import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zCompanyPage, zCompanyDetail, zCompanyMarketPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const companySearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  sector: z.string().max(100).optional(),
  index: z
    .string()
    .regex(
      /^(|NIFTY_50|NIFTY_NEXT_50|NIFTY_100|NIFTY_200|NIFTY_500|NIFTY_MIDCAP_50|NIFTY_MIDCAP_100|NIFTY_MIDCAP_150|NIFTY_SMALLCAP_50|NIFTY_SMALLCAP_100|NIFTY_SMALLCAP_250)$/,
    )
    .default("NIFTY_50"),
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
      if (filters.index) params.set("index", filters.index);
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

export function companyQuery(id: string) {
  return queryOptions({
    queryKey: ["app", "company", id],
    queryFn: async ({ signal }) => {
      const result = zCompanyDetail.safeParse(
        await appRequest(`/api/app/companies/${encodeURIComponent(id)}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The company response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}

export const companyMarketSearchSchema = companySearchSchema.pick({
  q: true,
  page: true,
  page_size: true,
});
export type CompanyMarketSearch = z.infer<typeof companyMarketSearchSchema>;

export function companyMarketsQuery(filters: CompanyMarketSearch) {
  return queryOptions({
    queryKey: ["app", "company-markets", filters],
    refetchInterval: 5_000,
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: filters.q, page: String(filters.page) });
      tableParams(params, filters);
      const result = zCompanyMarketPage.safeParse(
        await appRequest(`/api/app/markets/companies?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The company market response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
