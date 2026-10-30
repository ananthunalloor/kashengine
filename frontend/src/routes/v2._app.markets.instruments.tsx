import { createFileRoute } from "@tanstack/react-router";

import { exchangeInstrumentsQuery } from "../shared/api/exchangeInstruments";
import { MarketInstrumentsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/markets/instruments")({
  beforeLoad: ({ context }) =>
    context.queryClient.ensureQueryData(
      exchangeInstrumentsQuery({
        q: "",
        page: 1,
        page_size: 25,
        exchange: "",
        segment: "",
        instrument_type: "",
      }),
    ),
  component: MarketInstrumentsPage,
});
