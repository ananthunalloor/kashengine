import { createFileRoute } from "@tanstack/react-router";

import { opsPageQuery, opsSearchSchema } from "../shared/api/opsWorkspace";
import { OpsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/ops/")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(opsPageQuery("overview/", opsSearchSchema.parse({}))),
  component: () => <OpsPage path="ops/" />,
});
