import { createFileRoute } from "@tanstack/react-router";

import { newsQuery } from "../shared/api/news";
import { NewsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/news")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(
      newsQuery({ q: "", source: "", coverage: "", sentiment: "", page: 1, page_size: 25 }),
    ),
  component: NewsPage,
});
