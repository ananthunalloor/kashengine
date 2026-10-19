import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import type { Session } from "./generated/types.gen";
import { zSession } from "./generated/zod.gen";

export const sessionQuery = queryOptions({
  queryKey: ["app", "session"],
  queryFn: async ({ signal }): Promise<Session> => {
    const body = await appRequest("/api/app/session", { signal });
    const result = zSession.safeParse(body);
    if (!result.success) {
      throw new ApiError(
        "contract",
        "The session response does not match this app. Reload the page.",
      );
    }
    return result.data;
  },
  staleTime: 30_000,
});
