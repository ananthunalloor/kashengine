import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Audit } from "../features/ops/Audit";
import { ApiError } from "../shared/api/errors";
import { auditQuery, auditSearchSchema } from "../shared/api/ops";
import type { AuditSearch } from "../shared/api/ops";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ops/audit/")({
  validateSearch: (search): AuditSearch => auditSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(auditQuery(deps)),
  beforeLoad: ({ context }) => {
    if (!context.session.is_staff)
      throw new ApiError("forbidden", "Staff access is required for Ops.", {
        code: "feature_not_available",
        status: 403,
      });
  },
  component: AuditPage,
  pendingComponent: () => <AppLoading withinShell label="audit trail" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Audit" />,
});

function AuditPage() {
  const filters = Route.useSearch();
  const navigate = Route.useNavigate();
  const { data, error, refetch } = useSuspenseQuery(auditQuery(filters));
  if (error)
    return (
      <AppError
        error={error}
        reset={() => void refetch()}
        onRetry={() => void refetch()}
        withinShell
        section="Audit"
      />
    );
  return (
    <Audit
      data={data}
      filters={filters}
      onFilter={(search, replace) => void navigate({ search, replace })}
    />
  );
}
