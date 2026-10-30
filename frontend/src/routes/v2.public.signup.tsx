import { createFileRoute } from "@tanstack/react-router";

import { SignupPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/public/signup")({
  component: SignupPage,
});
