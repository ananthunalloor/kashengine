import { NavLink } from "@mantine/core";
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

import type { IconType } from "react-icons";

type OpsPage = readonly [path: string, label: string, icon: IconType];

const sections = [
  {
    id: "activity",
    label: "Activity",
    pages: [
      ["", "Overview", LuGauge],
      ["jobs/", "Jobs", LuWorkflow],
      ["runs/", "Task runs", LuActivity],
      ["logs/", "Logs", LuScrollText],
      ["metrics/", "Metrics", LuChartColumn],
      ["schedule/", "Schedule", LuCalendarClock],
    ],
  },
  {
    id: "access",
    label: "Access",
    pages: [
      ["users/", "Users", LuUsers],
      ["subscriptions/", "Subscriptions", LuWalletCards],
      ["logins/", "Logins", LuShieldCheck],
      ["audit/", "Audit trail", LuClipboardList],
    ],
  },
  {
    id: "data",
    label: "Data & configuration",
    pages: [
      ["feeds/", "Feeds", LuNewspaper],
      ["instruments/", "Instruments", LuListChecks],
      ["config/", "Configuration", LuFileSliders],
      ["settings/", "Settings", LuSettings2],
      ["backups/", "Backups", LuDatabaseBackup],
    ],
  },
] as const;

const pages: readonly OpsPage[] = sections.reduce<OpsPage[]>(
  (allPages, { pages: sectionPages }) => {
    allPages.push(...sectionPages);
    return allPages;
  },
  [],
);

export function opsPageIcon(path: string) {
  return pages.find(([prefix]) => prefix && path.startsWith(prefix))?.[2] ?? LuGauge;
}

export function OpsNavigation({
  superuser,
  pathname,
  onNavigate,
}: {
  superuser: boolean;
  pathname: string;
  onNavigate: () => void;
}) {
  const visibleSections = sections
    .map((section) => ({
      ...section,
      pages: section.pages.filter(([path]) => path !== "backups/" || superuser),
    }))
    .filter(({ pages: sectionPages }) => sectionPages.length > 0);
  return (
    <>
      <nav className="ops-navigation" aria-label="Operations options">
        {visibleSections.map(({ id, label, pages: sectionPages }) => {
          return (
            <section className="ops-navigation-section" key={id}>
              <p className="ops-navigation-heading">{label}</p>
              {sectionPages.map(([path, pageLabel, Icon]) => {
                const href = `/ops/${path}`;
                const pageActive =
                  pathname === href || (path !== "" && pathname.startsWith(href));
                return (
                  <NavLink
                    className="ops-page-navlink"
                    key={path}
                    component={AppLink}
                    href={href}
                    label={pageLabel}
                    active={pageActive}
                    aria-current={pageActive ? "page" : undefined}
                    onClick={onNavigate}
                    leftSection={<Icon aria-hidden="true" />}
                  />
                );
              })}
            </section>
          );
        })}
      </nav>
    </>
  );
}
