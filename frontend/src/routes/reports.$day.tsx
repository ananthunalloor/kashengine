import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { ReportView } from "../features/reports/Reports";
import { reportQuery } from "../shared/api/reports";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/reports/$day")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(reportQuery(params.day)),
  component: ReportPage,
  pendingComponent: () => <AppLoading withinShell />,
  errorComponent: (props) => <AppError {...props} withinShell />,
});

function ReportPage() {
  const { day } = Route.useParams();
  const { data } = useSuspenseQuery(reportQuery(day));
  return <ReportView report={data} />;
}
