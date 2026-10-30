import { createFileRoute } from "@tanstack/react-router";

import { VerifyEmailPage } from "../v2/pages/PublicExtras";

export const Route = createFileRoute("/v2/public/verify-email/$token")({
  component: VerifyEmailRoute,
});

function VerifyEmailRoute() {
  const { token } = Route.useParams();
  return <VerifyEmailPage token={token} />;
}
