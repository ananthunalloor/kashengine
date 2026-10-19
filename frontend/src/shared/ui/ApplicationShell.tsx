import {
  Alert,
  Anchor,
  Burger,
  Button,
  Group,
  NavLink,
  Stack,
  Text,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useRef } from "react";
import type { ReactNode } from "react";
import {
  LuActivity,
  LuArrowUpRight,
  LuBuilding2,
  LuChartNoAxesCombined,
  LuCircleUserRound,
  LuClipboardList,
  LuFileText,
  LuHouse,
  LuLayoutDashboard,
  LuLogOut,
  LuMoon,
  LuNewspaper,
  LuSend,
  LuSettings2,
  LuShieldCheck,
  LuSparkles,
  LuSun,
} from "react-icons/lu";
import type { IconType } from "react-icons";

import { csrfToken } from "../api/client";
import type { Session } from "../api/generated/types.gen";

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
  const token = csrfToken();
  const burger = useRef<HTMLButtonElement>(null);

  return (
    <div className="app-shell">
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
            <a href="/app/" className="app-brand" aria-label="Kash Engine">
              <span className="app-brand-mark" aria-hidden="true">
                k.
              </span>
              <span>
                kash<span className="app-brand-light">engine</span>
              </span>
            </a>
          </Group>
          <Group gap="xs">
            <span className="workspace-badge app-desktop-only">
              <LuShieldCheck aria-hidden="true" />
              Private workspace
            </span>
            <Text size="sm" className="app-desktop-only">
              {session.username}
            </Text>
            <Button
              variant="default"
              size="compact-sm"
              onClick={() => setColorScheme(colorScheme === "dark" ? "light" : "dark")}
              aria-label="Toggle color scheme"
              leftSection={
                colorScheme === "dark" ? (
                  <LuSun aria-hidden="true" />
                ) : (
                  <LuMoon aria-hidden="true" />
                )
              }
            >
              {colorScheme === "dark" ? "Light theme" : "Dark theme"}
            </Button>
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
            <LuSparkles aria-hidden="true" />
          </span>
          <div>
            <strong>Your workspace</strong>
            <span>Market intelligence</span>
          </div>
        </div>
        <p className="navigation-label">Workspace</p>
        <nav aria-label="Main">
          <NavLink
            href="/app/"
            label="React preview"
            active={pathname === "/app/"}
            aria-current={pathname === "/app/" ? "page" : undefined}
            onClick={close}
            leftSection={<LuLayoutDashboard aria-hidden="true" />}
          />
          {session.navigation.map((item) => {
            const migrated = [
              "/dashboard/",
              "/account/",
              "/reports/",
              "/news/",
              "/ipos/",
              "/markets/",
              "/companies/",
              "/delivery/",
            ].includes(item.url);
            const url = migrated ? `/app${item.url}` : item.url;
            const active = pathname === url || (migrated && pathname.startsWith(url));
            const Icon = navigationIcons[item.url] ?? LuSettings2;
            return (
              <NavLink
                key={item.url}
                href={url}
                label={item.label}
                active={active}
                aria-current={active ? "page" : undefined}
                onClick={close}
                leftSection={<Icon aria-hidden="true" />}
                rightSection={!migrated && <LuArrowUpRight aria-hidden="true" />}
              />
            );
          })}
          {session.is_staff && (
            <NavLink
              href="/app/ops/runs/"
              label="Task runs"
              active={pathname.startsWith("/app/ops/runs/")}
              aria-current={pathname.startsWith("/app/ops/runs/") ? "page" : undefined}
              onClick={close}
              leftSection={<LuActivity aria-hidden="true" />}
            />
          )}
          {session.is_staff && (
            <NavLink
              href="/app/ops/audit/"
              label="Audit trail"
              active={pathname.startsWith("/app/ops/audit/")}
              aria-current={pathname.startsWith("/app/ops/audit/") ? "page" : undefined}
              onClick={close}
              leftSection={<LuClipboardList aria-hidden="true" />}
            />
          )}
        </nav>
        <Stack mt="auto" p="xs" gap="xs">
          <span className="account-avatar" aria-hidden="true">
            {session.username.slice(0, 2).toUpperCase()}
          </span>
          <Text size="sm" c="dimmed">
            Signed in as {session.username}
          </Text>
          <form action={session.logout_url} method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value={token ?? ""} />
            <Button
              type="submit"
              variant="default"
              fullWidth
              disabled={!token}
              leftSection={<LuLogOut aria-hidden="true" />}
            >
              Log out
            </Button>
          </form>
          {!token && (
            <Text size="xs" role="alert">
              Reload the page to enable secure logout.
            </Text>
          )}
        </Stack>
      </aside>
      <main className="app-main" id="main" tabIndex={-1}>
        {session.notice && (
          <Alert color="yellow" title="Your subscription" role="status" mb="md">
            {session.notice} <Anchor href="/app/account/">See your account</Anchor>.
          </Alert>
        )}
        {children}
        <Text component="footer" size="xs" c="dimmed" mt="xl" py="lg">
          Market signals are informational, not investment advice. GMP is unofficial data.
        </Text>
      </main>
    </div>
  );
}
