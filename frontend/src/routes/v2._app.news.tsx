import { createFileRoute } from "@tanstack/react-router";

import { NewsPage } from "../v2/pages/News";

export const Route = createFileRoute("/v2/_app/news")({
  component: NewsPage,
});
