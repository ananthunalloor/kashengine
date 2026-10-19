const opsDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function OpsTime({ value }: { value: string | null }) {
  return value ? <time dateTime={value}>{opsDate.format(new Date(value))} IST</time> : "\u2013";
}
