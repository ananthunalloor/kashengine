import { createFileRoute } from "@tanstack/react-router";

import { CompaniesPage } from "../v2/pages/Companies";

export const Route = createFileRoute("/v2/_app/companies/")({
  component: CompaniesPage,
});
