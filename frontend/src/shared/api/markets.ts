import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zMarkets } from "./generated/zod.gen";

export function marketsQuery() {
  return queryOptions({
    queryKey: ["app", "markets"],
    queryFn: async ({ signal }) => {
      const result = zMarkets.safeParse(await appRequest("/api/app/markets", { signal }));
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Markets response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
