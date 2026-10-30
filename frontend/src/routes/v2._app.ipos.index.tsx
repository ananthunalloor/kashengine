import { createFileRoute } from "@tanstack/react-router";

import { iposQuery } from "../shared/api/ipos";
import { IposPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/ipos/")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(
      iposQuery({ q: "", status: "", verdict: "", category: "", page: 1, page_size: 25 }),
    ),
  component: IposPage,
});
