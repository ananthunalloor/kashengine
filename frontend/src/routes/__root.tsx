import { useSuspenseQuery } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";

import { sessionQuery } from "../shared/api/session";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);

  useEffect(() => {
    document.title = "React preview | Kash Engine";
    document.querySelector<HTMLElement>("#main h1")?.focus();
  }, []);

  return (
    <ApplicationShell session={session}>
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
