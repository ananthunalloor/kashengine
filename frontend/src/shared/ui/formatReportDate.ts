const reportDate = new Intl.DateTimeFormat("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});

export function formatReportDate(day: string) {
  return reportDate.format(new Date(`${day}T00:00:00+05:30`));
}
