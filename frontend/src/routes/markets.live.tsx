import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { CompanyMarkets } from "../features/markets/CompanyMarkets";
import { companyMarketsQuery, companyMarketSearchSchema } from "../shared/api/companies";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/markets/live")({
  validateSearch: (search) => companyMarketSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(companyMarketsQuery(deps)),
  component: CompanyMarketRoute,
  pendingComponent: () => <AppLoading withinShell label="Company market data" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Markets" />,
});

function CompanyMarketRoute() {
  const filters = Route.useSearch();
  const navigate = Route.useNavigate();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(companyMarketsQuery(filters));
  return (
    <CompanyMarkets
      key={filters.q}
      data={data}
      filters={filters}
      canViewCompanies={session.features.includes("companies")}
      onFilter={(search) => void navigate({ search })}
    />
  );
}
