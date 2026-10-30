import { createFileRoute } from "@tanstack/react-router";

import { LoginPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/public/login")({
  component: LoginPage,
});
