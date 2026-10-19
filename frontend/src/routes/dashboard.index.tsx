import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Today } from "../features/today/Today";
import { todayQuery } from "../shared/api/today";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/dashboard/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(todayQuery()),
  component: TodayPage,
  pendingComponent: () => <AppLoading withinShell label="Today" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Today" />,
});

function TodayPage() {
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(todayQuery());
  return <Today data={data} session={session} />;
}
