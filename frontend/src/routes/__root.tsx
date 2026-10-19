import { useSuspenseQuery } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet, useRouterState } from "@tanstack/react-router";

import { sessionQuery } from "../shared/api/session";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <ApplicationShell session={session} pathname={`/app${pathname}`}>
      <Outlet />
    </ApplicationShell>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  beforeLoad: async ({ context }) => ({
    session: await context.queryClient.ensureQueryData(sessionQuery),
  }),
  component: RootLayout,
  pendingComponent: AppLoading,
  errorComponent: AppError,
  pendingMs: 150,
});
