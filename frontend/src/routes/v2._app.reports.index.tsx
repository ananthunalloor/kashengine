import { createFileRoute } from "@tanstack/react-router";

import { ReportsPage } from "../v2/pages/Reports";

export const Route = createFileRoute("/v2/_app/reports/")({
  component: ReportsPage,
});
