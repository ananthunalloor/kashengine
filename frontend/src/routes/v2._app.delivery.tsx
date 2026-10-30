import { createFileRoute } from "@tanstack/react-router";

import { deliveryQuery } from "../shared/api/delivery";
import { DeliveryPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/delivery")({
  beforeLoad: ({ context }) => context.queryClient.ensureQueryData(deliveryQuery()),
  component: DeliveryPage,
});
