import { createFileRoute } from "@tanstack/react-router";

import { accountQuery } from "../shared/api/account";
import { AccountPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/account")({
  beforeLoad: ({ context }) => context.queryClient.ensureQueryData(accountQuery()),
  component: AccountPage,
});
