import { useSuspenseQuery } from "@tanstack/react-query";
import { Alert } from "@mantine/core";
import { z } from "zod";
import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet, useRouterState } from "@tanstack/react-router";

import { sessionQuery } from "../shared/api/session";
import { zOpsMessage } from "../shared/api/generated/zod.gen";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const historyState = useRouterState({ select: (state) => state.location.state });
  const notice = z.object({ opsNotice: z.array(zOpsMessage).optional() }).safeParse(historyState);

  return (
    <ApplicationShell session={session} pathname={`/app${pathname}`}>
      {notice.success && notice.data.opsNotice?.length ? (
        <div role="status">
          {notice.data.opsNotice.map((message, index) => (
            <Alert
              key={index}
              title={message.level}
              color={message.level === "error" ? "red" : "violet"}
            >
              {message.text}
            </Alert>
          ))}
        </div>
      ) : null}
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
