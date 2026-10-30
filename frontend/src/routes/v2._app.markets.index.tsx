import { createFileRoute } from "@tanstack/react-router";

import { marketsQuery } from "../shared/api/markets";
import { calendarQuery } from "../shared/api/calendar";
import { companyMarketsQuery } from "../shared/api/companies";
import { MarketsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/markets/")({
  beforeLoad: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(marketsQuery()),
      context.queryClient.ensureQueryData(calendarQuery(new Date().getFullYear())),
      context.queryClient.ensureQueryData(companyMarketsQuery({ q: "", page: 1, page_size: 25 })),
    ]),
  component: MarketsPage,
});
