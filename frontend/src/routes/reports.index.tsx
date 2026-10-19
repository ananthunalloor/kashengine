import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { ReportsList } from "../features/reports/Reports";
import { reportsQuery, reportSearchSchema } from "../shared/api/reports";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/reports/")({
  validateSearch: (search) => reportSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(reportsQuery(deps)),
  component: ReportsPage,
  pendingComponent: () => <AppLoading withinShell />,
  errorComponent: (props) => <AppError {...props} withinShell />,
});

function ReportsPage() {
  const filters = Route.useSearch();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(reportsQuery(filters));
  const navigate = Route.useNavigate();
  return (
    <ReportsList
      data={data}
      isStaff={session.is_staff}
      filters={filters}
      onFilter={(search, replace) => {
        void navigate({ search, replace });
      }}
    />
  );
}
