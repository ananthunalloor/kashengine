import { NavLink, Tabs } from "@mantine/core";
import { useEffect, useRef, useState } from "react";
import {
  LuActivity,
  LuCalendarClock,
  LuChartColumn,
  LuClipboardList,
  LuDatabaseBackup,
  LuFileSliders,
  LuGauge,
  LuKeyRound,
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
import type { ReactNode } from "react";

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
      ["invites/", "Invite codes", LuKeyRound],
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
    <nav className="ops-navigation" aria-label="Operations options">
      {visibleSections.map(({ id, label, pages: sectionPages }) => {
        const [defaultPath, , Icon] = sectionPages[0];
        const href = `/ops/${defaultPath}`;
        const sectionActive = sectionPages.some(([path]) =>
          path === "" ? pathname === "/ops/" : pathname.startsWith(`/ops/${path}`),
        );

        return (
          <NavLink
            className="ops-section-navlink"
            key={id}
            component={AppLink}
            href={href}
            activeOptions={{ exact: true }}
            label={label}
            leftSection={<Icon aria-hidden="true" />}
            active={sectionActive}
            aria-current={pathname === href ? "page" : undefined}
            onClick={onNavigate}
          />
        );
      })}
    </nav>
  );
}

export function OpsPageTabs({
  superuser,
  pathname,
  children,
}: {
  superuser: boolean;
  pathname: string;
  children: ReactNode;
}) {
  const tabList = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const updateStuck = () => {
      const element = tabList.current;
      if (!element) {
        setStuck(false);
        return;
      }
      const top = Number.parseFloat(getComputedStyle(element).top);
      setStuck(element.getBoundingClientRect().top <= top);
    };
    updateStuck();
    window.addEventListener("scroll", updateStuck, { passive: true });
    window.addEventListener("resize", updateStuck);
    return () => {
      window.removeEventListener("scroll", updateStuck);
      window.removeEventListener("resize", updateStuck);
    };
  }, [pathname]);
  const visibleSections = sections
    .map((section) => ({
      ...section,
      pages: section.pages.filter(([path]) => path !== "backups/" || superuser),
    }))
    .filter(({ pages: sectionPages }) => sectionPages.length > 0);
  const activeSection = visibleSections.find(({ pages: sectionPages }) =>
    sectionPages.some(([path]) =>
      path === "" ? pathname === "/ops/" : pathname.startsWith(`/ops/${path}`),
    ),
  );
  const activePage = activeSection?.pages.find(([path]) =>
    path === "" ? pathname === "/ops/" : pathname.startsWith(`/ops/${path}`),
  );

  if (!activeSection || !activePage) return <>{children}</>;

  const activeValue = `/ops/${activePage[0]}`;

  return (
    <Tabs className="ops-page-tabs" value={activeValue} keepMounted={false}>
      <Tabs.List ref={tabList} data-stuck={stuck} aria-label={`${activeSection.label} pages`}>
        {activeSection.pages.map(([path, label, Icon]) => {
          const value = `/ops/${path}`;
          return (
            <Tabs.Tab
              key={path}
              value={value}
              renderRoot={(props) => <AppLink {...props} href={value} />}
              leftSection={<Icon aria-hidden="true" />}
            >
              {label}
            </Tabs.Tab>
          );
        })}
      </Tabs.List>
      {activeSection.pages.map(([path]) => {
        const value = `/ops/${path}`;
        return (
          <Tabs.Panel className="ops-page-tab-panel" key={value} value={value}>
            {value === activeValue ? children : null}
          </Tabs.Panel>
        );
      })}
    </Tabs>
  );
}
