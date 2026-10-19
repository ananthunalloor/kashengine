import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { loginUrl } from "../shared/api/client";
import { ApiError, retryDelay, shouldRetry } from "../shared/api/errors";

function handleAuthError(error: Error) {
  if (error instanceof ApiError && error.kind === "unauthorized") {
    window.location.assign(loginUrl());
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleAuthError }),
  mutationCache: new MutationCache({ onError: handleAuthError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: shouldRetry,
      retryDelay,
      refetchOnWindowFocus: true,
    },
  },
});
