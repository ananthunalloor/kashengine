import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Ipos } from "../features/ipos/Ipos";
import { iposQuery, ipoSearchSchema } from "../shared/api/ipos";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ipos/")({
  validateSearch: (search) => ipoSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(iposQuery(deps)),
  component: IposPage,
  pendingComponent: () => <AppLoading withinShell label="IPOs" />,
  errorComponent: (props) => <AppError {...props} withinShell section="IPOs" />,
});

function IposPage() {
  const filters = Route.useSearch();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(iposQuery(filters));
  const navigate = Route.useNavigate();
  return (
    <Ipos
      data={data}
      filters={filters}
      isStaff={session.is_staff}
      onFilter={(search, replace) => {
        void navigate({ search, replace });
      }}
    />
  );
}
