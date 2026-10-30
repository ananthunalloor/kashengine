import { createFileRoute } from "@tanstack/react-router";

import { companiesQuery } from "../shared/api/companies";
import { CompaniesPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/companies/")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(
      companiesQuery({ q: "", page: 1, page_size: 25, index: "NIFTY_50" }),
    ),
  component: CompaniesPage,
});
