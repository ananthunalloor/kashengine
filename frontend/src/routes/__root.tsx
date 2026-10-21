import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { z } from "zod";
import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet, useRouterState } from "@tanstack/react-router";

import { sessionQuery } from "../shared/api/session";
import { zOpsMessage } from "../shared/api/generated/zod.gen";
import { ApplicationShell } from "../shared/ui/ApplicationShell";
import { AppError, AppLoading } from "../shared/ui/AppStatus";
import { PageNotFound } from "../shared/ui/PageNotFound";
import { OpsNotice } from "../features/ops/OpsStatus";
import { publishNotification } from "../shared/notifications";

const jobNotificationSchema = z.object({
  label: z.string(),
  status: z.enum(["success", "failure"]),
  error: z.string(),
  url: z.string().startsWith("/ops/runs/"),
});

function RootLayout() {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const queryClient = useQueryClient();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const historyState = useRouterState({ select: (state) => state.location.state });
  const notice = z.object({ opsNotice: z.array(zOpsMessage).optional() }).safeParse(historyState);

  useEffect(() => {
    if (!session.is_staff || typeof EventSource === "undefined") return;
    const stream = new EventSource("/api/app/notifications/");
    const onJob = (event: Event) => {
      let data: unknown;
      try {
        data = JSON.parse((event as MessageEvent<string>).data);
      } catch {
        return;
      }
      const parsed = jobNotificationSchema.safeParse(data);
      if (!parsed.success) return;
      const job = parsed.data;
      const failed = job.status === "failure";
      publishNotification({
        title: failed ? "Job failed" : "Job completed",
        message: failed ? `${job.label}: ${job.error || "The task failed."}` : job.label,
        tone: failed ? "error" : "success",
        href: job.url,
      });
      void queryClient.invalidateQueries();
    };
    stream.addEventListener("job", onJob);
    return () => {
      stream.removeEventListener("job", onJob);
      stream.close();
    };
  }, [queryClient, session.is_staff]);

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
