import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { RunDetail } from "../features/ops/RunDetail";
import { ApiError } from "../shared/api/errors";
import { runQuery } from "../shared/api/ops";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ops/runs/$id")({
  beforeLoad: ({ context }) => {
    if (!context.session.is_staff)
      throw new ApiError("forbidden", "Staff access is required for Ops.", {
        code: "feature_not_available",
        status: 403,
      });
  },
  loader: ({ context, params }) => context.queryClient.ensureQueryData(runQuery(params.id)),
  component: RunPage,
  pendingComponent: () => <AppLoading withinShell label="task run" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Task runs" />,
});

function RunPage() {
  const { id } = Route.useParams();
  const { data, error, isFetching, refetch } = useQuery(runQuery(id));
  if (error)
    return (
      <AppError
        error={error}
        reset={() => void refetch()}
        onRetry={() => void refetch()}
        withinShell
        section="Task runs"
      />
    );
  if (!data) return <AppLoading withinShell label="task run" />;
  return <RunDetail run={data} refreshing={isFetching} onRefresh={() => void refetch()} />;
}
