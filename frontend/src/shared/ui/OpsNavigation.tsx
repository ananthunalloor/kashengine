import {
  LuActivity,
  LuCalendarClock,
  LuChartColumn,
  LuClipboardList,
  LuDatabaseBackup,
  LuFileSliders,
  LuGauge,
  LuListChecks,
  LuNewspaper,
  LuScrollText,
  LuSettings2,
  LuShieldCheck,
  LuUsers,
  LuWalletCards,
  LuWorkflow,
} from "react-icons/lu";
import { AppLink } from "./AppLink";

const pages = [
  ["", "Overview", LuGauge],
  ["jobs/", "Jobs", LuWorkflow],
  ["runs/", "Task runs", LuActivity],
  ["logs/", "Logs", LuScrollText],
  ["metrics/", "Metrics", LuChartColumn],
  ["users/", "Users", LuUsers],
  ["subscriptions/", "Subscriptions", LuWalletCards],
  ["logins/", "Logins", LuShieldCheck],
  ["audit/", "Audit trail", LuClipboardList],
  ["settings/", "Settings", LuSettings2],
  ["schedule/", "Schedule", LuCalendarClock],
  ["feeds/", "Feeds", LuNewspaper],
  ["instruments/", "Instruments", LuListChecks],
  ["config/", "Configuration", LuFileSliders],
  ["backups/", "Backups", LuDatabaseBackup],
] as const;

export function opsPageIcon(path: string) {
  return pages.find(([prefix]) => prefix && path.startsWith(prefix))?.[2] ?? LuGauge;
}

export function OpsNavigation({ superuser, pathname }: { superuser: boolean; pathname: string }) {
  return (
    <nav className="ops-navigation" aria-label="Operations">
      {pages
        .filter(([path]) => path !== "backups/" || superuser)
        .map(([path, label, Icon]) => (
          <AppLink
            key={path}
            href={`/ops/${path}`}
            aria-current={
              pathname === `/ops/${path}` || (path && pathname.startsWith(`/ops/${path}`))
                ? "page"
                : undefined
            }
          >
            <Icon aria-hidden="true" />
            {label}
          </AppLink>
        ))}
    </nav>
  );
}
