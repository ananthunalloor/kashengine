import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Watchlist } from "../features/companies/Watchlist";
import { watchlistQuery } from "../shared/api/watchlist";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/watchlist/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(watchlistQuery()),
  component: WatchlistPage,
  pendingComponent: () => <AppLoading withinShell label="watchlist" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Companies" />,
});

function WatchlistPage() {
  const { data } = useSuspenseQuery(watchlistQuery());
  const { session } = Route.useRouteContext();
  return <Watchlist items={data.items} marketsAvailable={session.features.includes("markets")} />;
}
