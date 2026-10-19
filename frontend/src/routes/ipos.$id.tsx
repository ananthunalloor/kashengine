import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { IpoView } from "../features/ipos/Ipos";
import { ipoQuery } from "../shared/api/ipos";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/ipos/$id")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(ipoQuery(params.id)),
  component: IpoPage,
  pendingComponent: () => <AppLoading withinShell label="IPO" />,
  errorComponent: (props) => <AppError {...props} withinShell section="IPOs" />,
});

function IpoPage() {
  const { id } = Route.useParams();
  const { data } = useSuspenseQuery(ipoQuery(id));
  return <IpoView ipo={data} />;
}
