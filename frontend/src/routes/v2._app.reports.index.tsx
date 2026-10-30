import { createFileRoute } from "@tanstack/react-router";

import { reportsQuery } from "../shared/api/reports";
import { ReportsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/reports/")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(reportsQuery({ page: 1, page_size: 25 })),
  component: ReportsPage,
});
