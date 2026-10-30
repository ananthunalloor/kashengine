import { createFileRoute } from "@tanstack/react-router";

import { MarketsPage } from "../v2/pages/Markets";

export const Route = createFileRoute("/v2/_app/markets/instruments")({
  component: () => <MarketsPage initialTab="instruments" />,
});
