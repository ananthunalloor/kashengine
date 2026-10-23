import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { CompanyView } from "../features/companies/Company";
import { companyQuery } from "../shared/api/companies";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/companies/$id")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(companyQuery(params.id)),
  component: CompanyPage,
  pendingComponent: () => <AppLoading withinShell label="Company" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Companies" />,
});

function CompanyPage() {
  const { id } = Route.useParams();
  const { data } = useSuspenseQuery(companyQuery(id));
  return <CompanyView data={data} />;
}
