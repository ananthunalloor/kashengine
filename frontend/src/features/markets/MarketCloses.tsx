import type { MarketQuote } from "../../shared/api/generated/types.gen";
import { DataTable } from "../../shared/ui/DataTable";
import { displayNumber } from "../../shared/ui/displayNumber";
import { MetricValue } from "../../shared/ui/MetricValue";

const tradingDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function MarketDate({ day }: { day: string }) {
  return <time dateTime={day}>{tradingDate.format(new Date(`${day}T00:00:00+05:30`))}</time>;
}

export function MarketCloses({
  quotes,
  label = "Saved market closes",
}: {
  quotes: MarketQuote[];
  label?: string;
}) {
  return (
    <DataTable
      data={quotes}
      label={label}
      empty={quotes.length ? undefined : "No saved closes yet."}
      columns={[
        {
          id: "name",
          label: "Instrument",
          value: (row) => row.name,
          render: (row) => <span className="table-primary">{row.name}</span>,
        },
        {
          id: "close",
          label: "Close",
          value: (row) => displayNumber(row.close),
          render: (row) => row.close,
        },
        {
          id: "change",
          label: "Change",
          value: (row) => displayNumber(row.change),
          render: (row) => <MetricValue kind="change" value={row.change} />,
        },
        {
          id: "day",
          label: "Trading day",
          value: (row) => row.day,
          render: (row) => <MarketDate day={row.day} />,
        },
      ]}
    />
  );
}
