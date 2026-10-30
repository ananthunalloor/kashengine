import { createFileRoute } from "@tanstack/react-router";

import { IpoDetailPage } from "../v2/pages/IpoDetail";

export const Route = createFileRoute("/v2/_app/ipos/$id")({
  component: Page,
});

function Page() {
  const { id } = Route.useParams();
  return <IpoDetailPage id={id} />;
}
