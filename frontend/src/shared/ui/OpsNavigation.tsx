const pages = [
  ["", "Overview"],
  ["jobs/", "Jobs"],
  ["runs/", "Task runs"],
  ["logs/", "Logs"],
  ["metrics/", "Metrics"],
  ["users/", "Users"],
  ["subscriptions/", "Subscriptions"],
  ["logins/", "Logins"],
  ["audit/", "Audit trail"],
  ["settings/", "Settings"],
  ["schedule/", "Schedule"],
  ["feeds/", "Feeds"],
  ["instruments/", "Instruments"],
  ["config/", "Configuration"],
  ["backups/", "Backups"],
] as const;

export function OpsNavigation({ superuser, pathname }: { superuser: boolean; pathname: string }) {
  return (
    <nav className="ops-navigation" aria-label="Operations">
      {pages
        .filter(([path]) => path !== "backups/" || superuser)
        .map(([path, label]) => (
          <a
            key={path}
            href={`/ops/${path}`}
            aria-current={pathname === `/ops/${path}` ? "page" : undefined}
          >
            {label}
          </a>
        ))}
    </nav>
  );
}
