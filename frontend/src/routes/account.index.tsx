import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { Account } from "../features/account/Account";
import { accountQuery } from "../shared/api/account";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/account/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(accountQuery()),
  component: AccountPage,
  pendingComponent: () => <AppLoading withinShell label="Account" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Account" />,
});

function AccountPage() {
  const { data } = useSuspenseQuery(accountQuery());
  return <Account data={data} />;
}
