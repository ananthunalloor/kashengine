import { createFileRoute } from "@tanstack/react-router";

import { Workspace } from "../features/ops/Workspace";
import { ApiError } from "../shared/api/errors";
import { opsPageQuery, opsSearchSchema } from "../shared/api/opsWorkspace";
import type { OpsSearch } from "../shared/api/opsWorkspace";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ops/$")({
  validateSearch: (search): OpsSearch => opsSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, params, deps }) =>
    context.queryClient.ensureQueryData(
      opsPageQuery(`${params._splat?.replace(/\/$/, "")}/`, deps),
    ),
  beforeLoad: ({ context, params }) => {
    if (
      !context.session.is_staff ||
      (params._splat?.replace(/\/$/, "") === "backups" && !context.session.is_superuser)
    )
      throw new ApiError("forbidden", "This Ops page requires additional permissions.", {
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
  const params = Route.useParams();
  const navigate = Route.useNavigate();
  return (
    <Workspace
      path={`${params._splat?.replace(/\/$/, "")}/`}
      filters={filters}
      onFilter={(search) => void navigate({ search })}
    />
  );
}
