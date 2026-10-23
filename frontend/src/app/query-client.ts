import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { loginUrl } from "../shared/api/client";
import { ApiError, retryDelay, shouldRetry } from "../shared/api/errors";
import { notifyError } from "../shared/ui/notifications";

function handleRequestError(error: Error) {
  if (error instanceof ApiError && error.kind === "unauthorized") {
    window.location.assign(loginUrl());
    return;
  }
  notifyError(error, "Request failed");
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleRequestError }),
  mutationCache: new MutationCache({ onError: handleRequestError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: shouldRetry,
      retryDelay,
      refetchOnWindowFocus: true,
    },
  },
});
