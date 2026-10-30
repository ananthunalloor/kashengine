import {
  ActionIcon,
  AppShell,
  Avatar,
  Burger,
  Divider,
  Group,
  Kbd,
  Menu,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure, useLocalStorage } from "@mantine/hooks";
import { Spotlight, spotlight } from "@mantine/spotlight";
import type { SpotlightActionData } from "@mantine/spotlight";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LuBuilding2,
  LuChartCandlestick,
  LuChevronsLeft,
  LuChevronsRight,
  LuBookOpen,
  LuFileText,
  LuLayoutDashboard,
  LuLogOut,
  LuMoon,
  LuNewspaper,
  LuRocket,
  LuSearch,
  LuSend,
  LuSettings2,
  LuShieldCheck,
  LuSun,
  LuUser,
} from "react-icons/lu";
import { useState } from "react";
import type { ReactNode } from "react";

import { sessionQuery } from "../../shared/api/session";
import type { Session } from "../../shared/api/generated/types.gen";
import { csrfToken } from "../../shared/api/client";
import { useLiveQuotes } from "../../shared/api/liveQuotes";
import { AppLink } from "../../shared/ui/AppLink";
import { OpsNavigation } from "../../shared/ui/OpsNavigation";
import { TradingCalendarModal } from "./TradingCalendarModal";

export type NavItem = { label: string; href: string; icon: ReactNode };

export const primaryNav: NavItem[] = [
  { label: "Today", href: "/v2/today/", icon: <LuLayoutDashboard /> },
  { label: "Reports", href: "/v2/reports/", icon: <LuFileText /> },
  { label: "News", href: "/v2/news/", icon: <LuNewspaper /> },
  { label: "IPOs", href: "/v2/ipos/", icon: <LuRocket /> },
  { label: "Markets", href: "/v2/markets/", icon: <LuChartCandlestick /> },
  { label: "Companies", href: "/v2/companies/", icon: <LuBuilding2 /> },
  { label: "Delivery", href: "/v2/delivery/", icon: <LuSend /> },
];

function useIsActive() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (href: string) => pathname === href || pathname.startsWith(href);
}

function NavItems({ items, rail }: { items: NavItem[]; rail: boolean }) {
  const isActive = useIsActive();
  return (
    <>
      {items.map((item) => {
        const link = (
          <NavLink
            key={item.href}
            className="kv2-navlink"
            component={AppLink}
            href={item.href}
            label={item.label}
            leftSection={item.icon}
            active={isActive(item.href)}
            aria-label={rail ? item.label : undefined}
          />
        );
        return rail ? (
          <Tooltip key={item.href} label={item.label} position="right">
            {link}
          </Tooltip>
        ) : (
          link
        );
      })}
    </>
  );
}

function SearchTrigger() {
  return (
    <>
      <button type="button" className="kv2-search-trigger" onClick={() => spotlight.open()}>
        <LuSearch size={14} />
        <span>Search companies, IPOs, reports…</span>
        <Kbd size="xs">⌘K</Kbd>
      </button>
    </>
  );
}

function MarketPill() {
  const [opened, { open, close }] = useDisclosure(false);
  const { data: session } = useSuspenseQuery(sessionQuery);
  const live = useLiveQuotes([]);
  const market = session.market_calendar;
  const liveDetail = Object.entries(live.status?.segments ?? {})
    .map(([segment, status]) => `${segment}: ${status}`)
    .join(" · ");
  return (
    <>
      <Tooltip
        label={`${market.reason}${market.special_reason ? ` · ${market.special_reason}` : ""} · Feed ${live.connection}${liveDetail ? `: ${liveDetail}` : ""} · Open trading calendar`}
      >
        <button
          type="button"
          className="kv2-market-pill"
          onClick={open}
          aria-label={`NSE ${market.is_open ? "open" : market.status_key}; ${market.reason}; market feed ${live.connection}. Open trading calendar.`}
        >
          <span
            className="kv2-dot"
            style={{
              color:
                market.is_open && live.connection === "live"
                  ? "var(--kv2-gain)"
                  : "var(--kv2-text-muted)",
            }}
          />
          <strong>NSE {market.is_open ? "open" : market.status_key}</strong>
        </button>
      </Tooltip>
      <TradingCalendarModal opened={opened} onClose={close} />
    </>
  );
}

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme("light");
  return (
    <Tooltip label={scheme === "dark" ? "Light theme" : "Dark theme"}>
      <ActionIcon
        aria-label="Toggle colour theme"
        onClick={() => setColorScheme(scheme === "dark" ? "light" : "dark")}
      >
        {scheme === "dark" ? <LuSun /> : <LuMoon />}
      </ActionIcon>
    </Tooltip>
  );
}

function UserMenu({ session }: { session: Session }) {
  const initials = session.username.slice(0, 2).toUpperCase() || "U";
  return (
    <Menu width={220} position="bottom-end">
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Group gap={8} wrap="nowrap">
            <Avatar size={28} radius="xl" color="indigo" variant="filled">
              {initials}
            </Avatar>
            <Stack gap={0} visibleFrom="md">
              <Text size="xs" fw={600} lh={1.2}>
                {session.username}
              </Text>
              {session.is_staff ? (
                <Text size="10px" c="dimmed" lh={1.2}>
                  Staff
                </Text>
              ) : null}
            </Stack>
          </Group>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{session.email}</Menu.Label>
        <Menu.Item leftSection={<LuUser size={14} />} component={AppLink} href="/v2/account/">
          Account
        </Menu.Item>
        <Menu.Item leftSection={<LuSend size={14} />} component={AppLink} href="/v2/delivery/">
          Delivery
        </Menu.Item>
        <Menu.Item
          leftSection={<LuSettings2 size={14} />}
          component={AppLink}
          href="/v2/design-system/"
        >
          Design system
        </Menu.Item>
        <Menu.Divider />
        <form action={session.logout_url} method="post">
          <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken() ?? ""} />
          <Menu.Item
            component="button"
            type="submit"
            leftSection={<LuLogOut size={14} />}
            color="red"
          >
            Sign out
          </Menu.Item>
        </form>
      </Menu.Dropdown>
    </Menu>
  );
}

function useSpotlightActions(): SpotlightActionData[] {
  const navigate = useNavigate();
  const go = (to: string) => () => void navigate({ to });
  return [
    ...primaryNav.map((item) => ({
      id: item.href,
      label: item.label,
      description: "Go to page",
      leftSection: item.icon,
      onClick: go(item.href),
    })),
  ];
}

/** Authenticated v2 shell: 48px header, 220px navbar collapsing to a 56px rail, Spotlight. */
export function V2Shell({ children }: { children: ReactNode }) {
  const { data: session } = useSuspenseQuery(sessionQuery);
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure(false);
  const [rail, setRail] = useLocalStorage({ key: "kv2-nav-rail", defaultValue: false });
  const actions = useSpotlightActions();
  const [query, setQuery] = useState("");
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const inOps = pathname.startsWith("/v2/ops/");
  const [lastPath, setLastPath] = useState(pathname);
  if (lastPath !== pathname) {
    setLastPath(pathname);
    closeMobile();
  }

  return (
    <AppShell
      header={{ height: 48 }}
      navbar={{
        width: { base: 220, sm: rail ? 56 : 220 },
        breakpoint: "sm",
        collapsed: { mobile: !mobileOpened },
      }}
      padding={0}
    >
      <AppShell.Header className="kv2-header">
        <Group h="100%" px={12} gap={12} wrap="nowrap" justify="space-between">
          <Group gap={12} wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
              aria-label="Toggle navigation"
            />
            <AppLink href="/v2/today/" className="kv2-logo">
              <span className="kv2-logo-mark">k.</span>
              <span>kashengine</span>
            </AppLink>
            <Group visibleFrom="md" style={{ width: "min(320px, 100%)", minWidth: 0 }}>
              <SearchTrigger />
            </Group>
          </Group>
          <Group gap={6} wrap="nowrap">
            <ActionIcon aria-label="Search" hiddenFrom="md" onClick={() => spotlight.open()}>
              <LuSearch />
            </ActionIcon>
            <MarketPill />
            <ThemeToggle />
            <Divider orientation="vertical" my={10} visibleFrom="sm" />
            <UserMenu session={session} />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar className={`kv2-navbar ${rail ? "kv2-rail" : ""}`} p={8}>
        <AppShell.Section grow component={ScrollArea} scrollbarSize={6}>
          <Stack gap={8}>
            <div className="kv2-sidebar-top">
              <Group justify="space-between" gap={4} wrap="nowrap">
                {!rail ? (
                  <Stack gap={2}>
                    <Text size="xs" fw={600}>
                      {inOps ? "Operations" : "Workspace"}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {inOps ? "Staff-only tools" : "Market research"}
                    </Text>
                  </Stack>
                ) : null}
                <Tooltip label={rail ? "Expand sidebar" : "Collapse sidebar"} position="right">
                  <ActionIcon
                    aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
                    onClick={() => setRail(!rail)}
                    variant="subtle"
                  >
                    {rail ? <LuChevronsRight /> : <LuChevronsLeft />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            </div>
            {inOps ? (
              <OpsNavigation
                superuser={session.is_superuser}
                pathname={pathname}
                onNavigate={closeMobile}
                basePath="/v2/ops/"
                rail={rail}
                showPages={false}
              />
            ) : (
              <NavItems items={primaryNav} rail={rail} />
            )}
          </Stack>
        </AppShell.Section>
        <AppShell.Section>
          <Divider my={8} />
          <Stack gap={2}>
            <NavItems
              items={[
                { label: "Account", href: "/v2/account/", icon: <LuUser /> },
                ...(inOps
                  ? [{ label: "Today", href: "/v2/today/", icon: <LuLayoutDashboard /> }]
                  : []),
              ]}
              rail={rail}
            />
            {session.is_staff && !inOps ? (
              <Tooltip label="Operations console" position="right" disabled={!rail}>
                <NavLink
                  className="kv2-navlink"
                  component="a"
                  href="/v2/ops/"
                  label="Operations"
                  leftSection={<LuShieldCheck />}
                  aria-label="Ops"
                />
              </Tooltip>
            ) : null}
          </Stack>
          <Divider my={8} />
          <Stack gap={2}>
            <Tooltip label="Settings" position="right" disabled={!rail}>
              <NavLink
                className="kv2-navlink"
                component={AppLink}
                href="/v2/account/"
                label="Settings"
                leftSection={<LuSettings2 />}
                aria-label="Settings"
              />
            </Tooltip>
            <Tooltip label="Documentation" position="right" disabled={!rail}>
              <NavLink
                className="kv2-navlink"
                component="a"
                href="/docs/"
                label="Documentation"
                leftSection={<LuBookOpen />}
                aria-label="Documentation"
              />
            </Tooltip>
          </Stack>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main className="kv2-shell-main">{children}</AppShell.Main>

      <Spotlight
        actions={actions}
        query={query}
        onQueryChange={setQuery}
        shortcut={["mod + K", "/"]}
        nothingFound="No matches"
        highlightQuery
        limit={8}
        searchProps={{
          leftSection: <LuSearch size={16} />,
          placeholder: "Search companies, IPOs, reports…",
        }}
        transitionProps={{ duration: 0 }}
      />
    </AppShell>
  );
}
