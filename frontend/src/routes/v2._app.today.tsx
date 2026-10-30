import { createFileRoute } from "@tanstack/react-router";

import { TodayPage } from "../v2/pages/Today";

export const Route = createFileRoute("/v2/_app/today")({
  component: TodayPage,
});
