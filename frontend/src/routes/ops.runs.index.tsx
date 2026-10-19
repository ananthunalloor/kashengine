import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Runs } from "../features/ops/Runs";
import { ApiError } from "../shared/api/errors";
import { runsQuery, runSearchSchema } from "../shared/api/ops";
import type { RunSearch } from "../shared/api/ops";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ops/runs/")({
  validateSearch: (search): RunSearch => runSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(runsQuery(deps)),
  beforeLoad: ({ context }) => {
    if (!context.session.is_staff)
      throw new ApiError("forbidden", "Staff access is required for Ops.", {
        code: "feature_not_available",
        status: 403,
      });
  },
  component: RunsPage,
  pendingComponent: () => <AppLoading withinShell label="task runs" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Task runs" />,
});

function RunsPage() {
  const filters = Route.useSearch();
  const navigate = Route.useNavigate();
  const { data, error, refetch } = useSuspenseQuery(runsQuery(filters));
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
  return (
    <Runs
      data={data}
      filters={filters}
      onFilter={(search, replace) => void navigate({ search, replace })}
    />
  );
}
