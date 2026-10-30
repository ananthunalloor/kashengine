import { createFileRoute } from "@tanstack/react-router";

import { reportQuery } from "../shared/api/reports";
import { ReportDetailPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/reports/$day")({
  beforeLoad: ({ context, params }) => context.queryClient.ensureQueryData(reportQuery(params.day)),
  component: Page,
});

function Page() {
  const { day } = Route.useParams();
  return <ReportDetailPage day={day} />;
}
