import { createFileRoute } from "@tanstack/react-router";

import { DeliveryPage } from "../v2/pages/Delivery";

export const Route = createFileRoute("/v2/_app/delivery")({
  component: DeliveryPage,
});
