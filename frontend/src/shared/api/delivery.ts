import { queryOptions } from "@tanstack/react-query";

import { appRequest } from "./client";
import { ApiError } from "./errors";
import { zDeliveryPage } from "./generated/zod.gen";

export function deliveryQuery() {
  return queryOptions({
    queryKey: ["app", "delivery"],
    queryFn: async ({ signal }) => {
      const result = zDeliveryPage.safeParse(await appRequest("/api/app/delivery", { signal }));
      if (!result.success)
        throw new ApiError(
          "contract",
          "The Delivery response does not match this app. Reload the page.",
        );
      return result.data;
    },
  });
}
