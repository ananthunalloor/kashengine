import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zToday } from "./generated/zod.gen";

export function todayQuery() {
  return queryOptions({
    queryKey: ["app", "today"],
    queryFn: async ({ signal }) => {
      const result = zToday.safeParse(await appRequest("/api/app/today", { signal }));
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Today response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
