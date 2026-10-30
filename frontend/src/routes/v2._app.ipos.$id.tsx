import { createFileRoute } from "@tanstack/react-router";

import { ipoQuery } from "../shared/api/ipos";
import { IpoDetailPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/ipos/$id")({
  beforeLoad: ({ context, params }) => context.queryClient.ensureQueryData(ipoQuery(params.id)),
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return <IpoDetailPage id={id} />;
}
