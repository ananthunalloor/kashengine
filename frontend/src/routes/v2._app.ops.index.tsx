import { createFileRoute } from "@tanstack/react-router";

import { OpsPage } from "../v2/pages/Ops";

export const Route = createFileRoute("/v2/_app/ops/")({
  component: () => <OpsPage path="ops/" />,
});
