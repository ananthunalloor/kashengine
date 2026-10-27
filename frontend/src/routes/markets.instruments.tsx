import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { ExchangeInstruments } from "../features/markets/ExchangeInstruments";
import {
  exchangeInstrumentSearchSchema,
  exchangeInstrumentsQuery,
} from "../shared/api/exchangeInstruments";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/markets/instruments")({
  validateSearch: (search) => exchangeInstrumentSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) =>
    context.queryClient.ensureQueryData(exchangeInstrumentsQuery(deps)),
  component: ExchangeInstrumentsPage,
  pendingComponent: () => <AppLoading withinShell label="exchange instruments" />,
  errorComponent: (props) => <AppError {...props} withinShell section="Markets" />,
});

function ExchangeInstrumentsPage() {
  const filters = Route.useSearch();
  const { data } = useSuspenseQuery(exchangeInstrumentsQuery(filters));
  const navigate = Route.useNavigate();
  return (
    <ExchangeInstruments
      data={data}
      filters={filters}
      onFilter={(search) => {
        void navigate({ search });
      }}
    />
  );
}
