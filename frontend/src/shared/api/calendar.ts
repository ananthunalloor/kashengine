import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zTradingCalendar } from "./generated/zod.gen";

export function calendarQuery(year: number) {
  return queryOptions({
    queryKey: ["app", "calendar", year],
    queryFn: async ({ signal }) => {
      const result = zTradingCalendar.safeParse(
        await appRequest(`/api/app/calendar?year=${year}`, { signal }),
      );
      if (!result.success)
        throw new ApiError(
          "contract",
          "The trading calendar does not match this app. Reload the page.",
        );
      return result.data;
    },
    staleTime: 30_000,
  });
}
