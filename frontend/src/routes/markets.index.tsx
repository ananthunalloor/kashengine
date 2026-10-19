import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Markets } from "../features/markets/Markets";
import { marketsQuery } from "../shared/api/markets";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/markets/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(marketsQuery()),
  component: MarketsPage,
  pendingComponent: () => <AppLoading withinShell label="Markets" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Markets" />,
});

function MarketsPage() {
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(marketsQuery());
  return <Markets data={data} isStaff={session.is_staff} />;
}
