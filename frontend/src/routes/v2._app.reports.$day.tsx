import { createFileRoute } from "@tanstack/react-router";

import { ReportDetailPage } from "../v2/pages/ReportDetail";

export const Route = createFileRoute("/v2/_app/reports/$day")({
  component: Page,
});

function Page() {
  const { day } = Route.useParams();
  return <ReportDetailPage day={day} />;
}
