import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

import { ReportsList } from "../features/reports/Reports";
import { reportsQuery } from "../shared/api/reports";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

const searchSchema = z.object({ page: z.coerce.number().int().positive().safe().default(1) });

export const Route = createFileRoute("/reports/")({
  validateSearch: (search) => searchSchema.parse(search),
  loaderDeps: ({ search }) => ({ page: search.page }),
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(reportsQuery(deps.page)),
  component: ReportsPage,
  pendingComponent: () => <AppLoading withinShell />,
  errorComponent: (props) => <AppError {...props} withinShell />,
});

function ReportsPage() {
  const { page } = Route.useSearch();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(reportsQuery(page));
  return <ReportsList data={data} isStaff={session.is_staff} />;
}
