import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zExchangeInstrumentPage } from "./generated/zod.gen";
import { pageSizeSchema, tableParams } from "./tableSearch";

export const exchangeInstrumentSearchSchema = z.object({
  q: z.string().trim().max(100).default(""),
  page: z.coerce.number().int().positive().safe().default(1),
  page_size: pageSizeSchema,
  exchange: z.enum(["", "NSE", "BSE"]).default(""),
  segment: z.string().max(20).default(""),
  instrument_type: z.string().max(30).default(""),
  sort: z
    .string()
    .regex(/^(|-?(exchange|trading_symbol|name|expiry))$/)
    .optional(),
});
export type ExchangeInstrumentSearch = z.infer<typeof exchangeInstrumentSearchSchema>;

export function exchangeInstrumentsQuery(filters: ExchangeInstrumentSearch) {
  return queryOptions({
    queryKey: ["app", "exchange-instruments", filters],
    queryFn: async ({ signal }) => {
      const params = new URLSearchParams({ q: filters.q, page: String(filters.page) });
      tableParams(params, filters);
      if (filters.exchange) params.set("exchange", filters.exchange);
      if (filters.segment) params.set("segment", filters.segment);
      if (filters.instrument_type) params.set("instrument_type", filters.instrument_type);
      const result = zExchangeInstrumentPage.safeParse(
        await appRequest(`/api/app/markets/instruments?${params}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The exchange instrument response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
