import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { z } from "zod";
import { useEffect } from "react";
import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router";

import { sessionQuery } from "../shared/api/session";
import { zOpsMessage } from "../shared/api/generated/zod.gen";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";
import { PageNotFound } from "../shared/ui/PageNotFound";
import { OpsNotice } from "../features/ops/OpsStatus";
import { LiveUpdates } from "../shared/ui/LiveUpdates";
import { notifyError } from "../shared/ui/notifications";

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const historyState = useRouterState({ select: (state) => state.location.state });
  const notice = z.object({ opsNotice: z.array(zOpsMessage).optional() }).safeParse(historyState);
  const client = useQueryClient();
  useEffect(() => {
    const delay = Math.min(
      2_147_483_647,
      Math.max(1000, Date.parse(session.market_calendar.next_change_at) - Date.now()),
    );
    const timer = window.setTimeout(() => {
      void client.fetchQuery({ ...sessionQuery, staleTime: 0 }).catch((error: unknown) => {
        notifyError(error, "Market status could not be refreshed");
      });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [client, session.market_calendar]);

  return (
    <ApplicationShell session={session} pathname={pathname}>
      {session.email_verified && <LiveUpdates staff={session.is_staff} />}
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
  beforeLoad: async ({ context, location }) => {
    const session = await context.queryClient.ensureQueryData(sessionQuery);
    if (!session.email_verified && location.pathname !== "/account/") {
      throw redirect({ to: "/account/" });
    }
    return { session };
  },
  component: RootLayout,
  pendingComponent: AppLoading,
  errorComponent: AppError,
  notFoundComponent: PageNotFound,
  pendingMs: 150,
});
