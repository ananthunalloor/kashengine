import { createFileRoute } from "@tanstack/react-router";

import { LandingPage } from "../v2/pages/Landing";

export const Route = createFileRoute("/v2/public/")({
  component: LandingPage,
});
