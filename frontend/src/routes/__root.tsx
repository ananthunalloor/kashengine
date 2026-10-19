import { useSuspenseQuery } from "@tanstack/react-query";
import { z } from "zod";
import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet, useRouterState } from "@tanstack/react-router";

import { sessionQuery } from "../shared/api/session";
import { zOpsMessage } from "../shared/api/generated/zod.gen";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";
import { PageNotFound } from "../shared/ui/PageNotFound";
import { OpsNotice } from "../features/ops/OpsStatus";

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const historyState = useRouterState({ select: (state) => state.location.state });
  const notice = z.object({ opsNotice: z.array(zOpsMessage).optional() }).safeParse(historyState);

  return (
    <ApplicationShell session={session} pathname={pathname}>
      {notice.success && notice.data.opsNotice?.length ? (
        <OpsNotice messages={notice.data.opsNotice} />
      ) : null}
      <div className="page-transition" key={pathname}>
        <Outlet />
      </div>
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
  notFoundComponent: PageNotFound,
  pendingMs: 150,
});
