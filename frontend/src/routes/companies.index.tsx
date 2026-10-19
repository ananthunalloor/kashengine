import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Companies } from "../features/companies/Companies";
import { companiesQuery, companySearchSchema } from "../shared/api/companies";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/companies/")({
  validateSearch: (search) => companySearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(companiesQuery(deps)),
  component: CompaniesPage,
  pendingComponent: () => <AppLoading withinShell label="companies" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Companies" />,
});

function CompaniesPage() {
  const filters = Route.useSearch();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(companiesQuery(filters));
  const navigate = Route.useNavigate();
  return (
    <Companies
      data={data}
      filters={filters}
      isStaff={session.is_staff}
      onFilter={(search, replace) => {
        void navigate({ search, replace });
      }}
    />
  );
}
