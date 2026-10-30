import { createFileRoute } from "@tanstack/react-router";

import { AccountPage } from "../v2/pages/Account";

export const Route = createFileRoute("/v2/_app/account")({
  component: AccountPage,
});
