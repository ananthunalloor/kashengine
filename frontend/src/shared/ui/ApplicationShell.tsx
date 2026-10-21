import {
  Alert,
  Anchor,
  Burger,
  Group,
  NavLink,
  Notification,
  Text,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  LuActivity,
  LuBuilding2,
  LuChartNoAxesCombined,
  LuCircleUserRound,
  LuClipboardList,
  LuFileText,
  LuHouse,
  LuMoon,
  LuNewspaper,
  LuSend,
  LuSettings2,
  LuShieldCheck,
  LuSparkles,
  LuSun,
} from "react-icons/lu";
import type { IconType } from "react-icons";

import type { Session } from "../api/generated/types.gen";
import { AccountMenu } from "./AccountMenu";
import { OpsNavigation } from "./OpsNavigation";
import { AppLink } from "./AppLink";
import { APP_NOTIFICATION_EVENT } from "../notifications";
import type { AppNotification } from "../notifications";

type DisplayNotification = AppNotification & { id: number };

const toneColors = {
  success: "green",
  error: "red",
  warning: "yellow",
  info: "blue",
} as const;

const navigationIcons: Record<string, IconType> = {
  "/dashboard/": LuHouse,
  "/reports/": LuFileText,
  "/news/": LuNewspaper,
  "/ipos/": LuActivity,
  "/markets/": LuChartNoAxesCombined,
  "/companies/": LuBuilding2,
  "/delivery/": LuSend,
  "/account/": LuCircleUserRound,
};

export function ApplicationShell({
  session,
  children,
  pathname = window.location.pathname,
}: {
  session: Session;
  children: ReactNode;
  pathname?: string;
}) {
  const [opened, { toggle, close }] = useDisclosure();
  // Mantine's transition reset injects a style element, which our CSP blocks.
  const { setColorScheme } = useMantineColorScheme({ keepTransitions: true });
  const colorScheme = useComputedColorScheme("light", { getInitialValueInEffect: true });
  const burger = useRef<HTMLButtonElement>(null);
  const [notifications, setNotifications] = useState<DisplayNotification[]>([]);
  const isOps = pathname.startsWith("/ops/");

  useEffect(() => {
    function onNotification(event: Event) {
      const notification = (event as CustomEvent<AppNotification>).detail;
      const id = Date.now() + Math.random();
      setNotifications((current) => [...current.slice(-3), { ...notification, id }]);
    }
    window.addEventListener(APP_NOTIFICATION_EVENT, onNotification);
    return () => window.removeEventListener(APP_NOTIFICATION_EVENT, onNotification);
  }, []);

  useEffect(() => {
    const timers = notifications.map(({ id }) =>
      window.setTimeout(
        () => setNotifications((current) => current.filter((item) => item.id !== id)),
        8000,
      ),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [notifications]);

  return (
    <div className={`app-shell${isOps ? " ops-shell" : ""}`}>
      <header className="app-header">
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={toggle}
              className="app-mobile-only"
              ref={burger}
              size="sm"
              aria-label={opened ? "Close navigation" : "Open navigation"}
              aria-expanded={opened}
              aria-controls="app-navigation"
            />
            <AppLink href="/" className="app-brand" aria-label="Kash Engine">
              <span className="app-brand-mark" aria-hidden="true">
                k.
              </span>
              <span>
                kash<span className="app-brand-light">engine</span>
              </span>
            </AppLink>
          </Group>
          <Group gap="xs">
            <span className="workspace-badge app-desktop-only">
              <LuShieldCheck aria-hidden="true" />
              {isOps ? "Operations console" : "Private workspace"}
            </span>
            <button
              type="button"
              className="header-icon-button"
              onClick={() => setColorScheme(colorScheme === "dark" ? "light" : "dark")}
              aria-label="Toggle color scheme"
              title={colorScheme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            >
              {colorScheme === "dark" ? (
                <LuSun aria-hidden="true" />
              ) : (
                <LuMoon aria-hidden="true" />
              )}
            </button>
            <AccountMenu session={session} pathname={pathname} />
          </Group>
        </Group>
      </header>
      <aside
        className="app-navigation"
        id="app-navigation"
        data-opened={opened}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            close();
            burger.current?.focus();
          }
        }}
      >
        <div className="workspace-card">
          <span className="workspace-icon">
            {isOps ? <LuSettings2 aria-hidden="true" /> : <LuSparkles aria-hidden="true" />}
          </span>
          <div>
            <strong>{isOps ? "Operations console" : "Your workspace"}</strong>
            <span>{isOps ? "Monitor, diagnose, manage" : "Market intelligence"}</span>
          </div>
        </div>
        <p className="navigation-label">Workspace</p>
        <nav aria-label="Main">
          {session.navigation.map((item) => {
            const url = item.url;
            const active = pathname === url || pathname.startsWith(url);
            const Icon = navigationIcons[item.url] ?? LuSettings2;
            return (
              <NavLink
                component={AppLink}
                key={item.url}
                href={url}
                label={item.label}
                active={active}
                aria-current={active ? "page" : undefined}
                onClick={close}
                leftSection={<Icon aria-hidden="true" />}
              />
            );
          })}
          {session.is_staff && !pathname.startsWith("/ops/") && (
            <NavLink
              component={AppLink}
              href="/ops/runs/"
              label="Task runs"
              active={pathname.startsWith("/ops/runs/")}
              aria-current={pathname.startsWith("/ops/runs/") ? "page" : undefined}
              onClick={close}
              leftSection={<LuActivity aria-hidden="true" />}
            />
          )}
          {session.is_staff && !pathname.startsWith("/ops/") && (
            <NavLink
              component={AppLink}
              href="/ops/audit/"
              label="Audit trail"
              active={pathname.startsWith("/ops/audit/")}
              aria-current={pathname.startsWith("/ops/audit/") ? "page" : undefined}
              onClick={close}
              leftSection={<LuClipboardList aria-hidden="true" />}
            />
          )}
        </nav>
      </aside>
      <main className="app-main" id="main" tabIndex={-1}>
        {session.is_staff && pathname.startsWith("/ops/") && (
          <OpsNavigation superuser={session.is_superuser} pathname={pathname} />
        )}
        {session.notice && (
          <Alert color="yellow" title="Your subscription" role="status" mb="md">
            {session.notice}{" "}
            <Anchor component={AppLink} href="/account/">
              See your account
            </Anchor>
            .
          </Alert>
        )}
        {children}
        <Text component="footer" size="xs" c="dimmed" mt="xl" py="lg">
          Market signals are informational, not investment advice. GMP is unofficial data.{" "}
          <Anchor component={AppLink} href="/">
            About Kash Engine
          </Anchor>
        </Text>
      </main>
      <div className="app-toast-viewport" aria-label="Notifications">
        {notifications.map((notification) => (
          <Notification
            key={notification.id}
            className="app-toast"
            data-tone={notification.tone}
            role={notification.tone === "error" ? "alert" : "status"}
            title={notification.title}
            color={toneColors[notification.tone]}
            closeButtonProps={{ "aria-label": "Dismiss notification" }}
            onClose={() =>
              setNotifications((current) => current.filter((item) => item.id !== notification.id))
            }
          >
            {notification.message}
            {notification.href && (
              <Anchor component={AppLink} href={notification.href} size="sm">
                View job run
              </Anchor>
            )}
          </Notification>
        ))}
      </div>
    </div>
  );
}
