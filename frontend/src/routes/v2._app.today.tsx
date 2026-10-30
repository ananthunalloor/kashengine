import { createFileRoute } from "@tanstack/react-router";

import { todayQuery } from "../shared/api/today";
import { TodayPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/today")({
  beforeLoad: ({ context }) => context.queryClient.ensureQueryData(todayQuery()),
  component: TodayPage,
});
