import { createFileRoute } from "@tanstack/react-router";

import { companyQuery } from "../shared/api/companies";
import { CompanyDetailPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/companies/$id")({
  beforeLoad: ({ context, params }) => context.queryClient.ensureQueryData(companyQuery(params.id)),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return <CompanyDetailPage id={id} />;
}
