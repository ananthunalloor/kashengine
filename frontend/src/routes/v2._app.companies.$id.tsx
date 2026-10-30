import { createFileRoute } from "@tanstack/react-router";

import { CompanyDetailPage } from "../v2/pages/CompanyDetail";

export const Route = createFileRoute("/v2/_app/companies/$id")({
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return <CompanyDetailPage id={id} />;
}
