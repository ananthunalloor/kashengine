import { createFileRoute } from "@tanstack/react-router";

import { SignupCompletePage } from "../v2/pages/PublicExtras";

export const Route = createFileRoute("/v2/public/signup-complete")({
  component: SignupCompletePage,
});
