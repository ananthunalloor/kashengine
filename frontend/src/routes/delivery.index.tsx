import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Delivery } from "../features/delivery/Delivery";
import { deliveryQuery } from "../shared/api/delivery";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/delivery/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(deliveryQuery()),
  component: DeliveryPage,
  pendingComponent: () => <AppLoading withinShell label="delivery" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Delivery" />,
});

function DeliveryPage() {
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(deliveryQuery());
  return (
    <Delivery
      data={data}
      isStaff={session.is_staff}
      canReadReports={session.features.includes("reports")}
    />
  );
}
