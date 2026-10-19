import { createFileRoute } from "@tanstack/react-router";

import { Workspace } from "../features/ops/Workspace";
import { ApiError } from "../shared/api/errors";
import { opsPageQuery, opsSearchSchema } from "../shared/api/opsWorkspace";
import type { OpsSearch } from "../shared/api/opsWorkspace";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ops/")({
  validateSearch: (search): OpsSearch => opsSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) =>
    context.queryClient.ensureQueryData(opsPageQuery("overview/", deps)),
  beforeLoad: ({ context }) => {
    if (!context.session.is_staff)
      throw new ApiError("forbidden", "Staff access is required for Ops.", {
        code: "feature_not_available",
        status: 403,
      });
  },
  component: Page,
  pendingComponent: () => <AppLoading withinShell label="operations" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Operations" />,
});

function Page() {
  const filters = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <Workspace
      path="overview/"
      filters={filters}
      onFilter={(search) => void navigate({ search })}
    />
  );
}
