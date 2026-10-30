import {
  ActionIcon,
  AppShell,
  Avatar,
  Badge,
  Burger,
  Divider,
  Group,
  Indicator,
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
import { useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LuBell,
  LuBuilding2,
  LuCalendarDays,
  LuChartCandlestick,
  LuChevronsLeft,
  LuChevronsRight,
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
  LuWifi,
} from "react-icons/lu";
import { useState } from "react";
import type { ReactNode } from "react";

import { AppLink } from "../../shared/ui/AppLink";
import { companies, marketStatus, notifications, sampleUser } from "../mock/data";
import { StatusBadge } from "./Status";
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
  return (
    <>
      <Tooltip label="Open trading calendar">
        <button type="button" className="kv2-market-pill" onClick={open}>
          <span
            className="kv2-dot"
            data-pulse={marketStatus.open}
            style={{ color: marketStatus.open ? "var(--kv2-gain)" : "var(--kv2-text-muted)" }}
          />
          <strong>{marketStatus.label}</strong>
          <Text span size="xs" c="dimmed" visibleFrom="lg">
            · {marketStatus.detail}
          </Text>
          <LuCalendarDays size={14} />
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

function NotificationsMenu() {
  return (
    <Menu width={300} position="bottom-end">
      <Menu.Target>
        <Indicator size={7} offset={7} color="red.6" processing={false}>
          <ActionIcon aria-label="Notifications">
            <LuBell />
          </ActionIcon>
        </Indicator>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Notifications</Menu.Label>
        {notifications.map((n) => (
          <Menu.Item key={n.id}>
            <Stack gap={0}>
              <Text size="sm">{n.title}</Text>
              <Text size="xs" c="dimmed">
                {n.time}
              </Text>
            </Stack>
          </Menu.Item>
        ))}
        <Menu.Divider />
        <Menu.Item component={AppLink} href="/v2/delivery/" c="var(--kv2-brand)">
          Delivery settings
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function UserMenu() {
  return (
    <Menu width={220} position="bottom-end">
      <Menu.Target>
        <UnstyledButton aria-label="Account menu">
          <Group gap={8} wrap="nowrap">
            <Avatar size={28} radius="xl" color="indigo" variant="filled">
              {sampleUser.initials}
            </Avatar>
            <Stack gap={0} visibleFrom="md">
              <Text size="xs" fw={600} lh={1.2}>
                {sampleUser.name}
              </Text>
              {sampleUser.staff ? (
                <Text size="10px" c="dimmed" lh={1.2}>
                  Staff
                </Text>
              ) : null}
            </Stack>
          </Group>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{sampleUser.email}</Menu.Label>
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
        <Menu.Item leftSection={<LuLogOut size={14} />} color="red">
          Sign out
        </Menu.Item>
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
    ...companies.slice(0, 12).map((c) => ({
      id: `co-${c.id}`,
      label: c.name,
      description: `${c.symbol} · ${c.sector}`,
      leftSection: <LuBuilding2 />,
      onClick: go(`/v2/companies/${c.id}/`),
    })),
  ];
}

/** Authenticated v2 shell: 48px header, 220px navbar collapsing to a 56px rail, Spotlight. */
export function V2Shell({ children }: { children: ReactNode }) {
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure(false);
  const [rail, setRail] = useLocalStorage({ key: "kv2-nav-rail", defaultValue: false });
  const actions = useSpotlightActions();
  const [query, setQuery] = useState("");
  const pathname = useRouterState({ select: (s) => s.location.pathname });
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
          <Group gap={8} wrap="nowrap" style={{ flex: "0 0 auto" }}>
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
              aria-label="Toggle navigation"
            />
            <AppLink href="/v2/today/" className="kv2-logo">
              <span className="kv2-logo-mark">k</span>
              <span>kashengine</span>
            </AppLink>
          </Group>
          <Group style={{ flex: 1, justifyContent: "center" }} visibleFrom="md">
            <SearchTrigger />
          </Group>
          <Group gap={6} wrap="nowrap">
            <ActionIcon aria-label="Search" hiddenFrom="md" onClick={() => spotlight.open()}>
              <LuSearch />
            </ActionIcon>
            <MarketPill />
            <Tooltip label="Live updates connected">
              <ActionIcon aria-label="Live connection status" visibleFrom="sm" c="var(--kv2-gain)">
                <LuWifi />
              </ActionIcon>
            </Tooltip>
            <ThemeToggle />
            <NotificationsMenu />
            <Divider orientation="vertical" my={10} visibleFrom="sm" />
            <UserMenu />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar className={`kv2-navbar ${rail ? "kv2-rail" : ""}`} p={8}>
        <AppShell.Section grow component={ScrollArea} scrollbarSize={6}>
          <Stack gap={2}>
            <NavItems items={primaryNav} rail={rail} />
          </Stack>
        </AppShell.Section>
        <AppShell.Section>
          <Divider my={8} />
          <Stack gap={2}>
            <NavItems
              items={[{ label: "Account", href: "/v2/account/", icon: <LuUser /> }]}
              rail={rail}
            />
            {sampleUser.staff ? (
              <Tooltip label="Operations console (v1)" position="right" disabled={!rail}>
                <NavLink
                  component="a"
                  href="/ops/"
                  label={
                    <Group gap={6} wrap="nowrap">
                      Ops
                      <Badge size="xs" variant="light" color="amber">
                        Staff
                      </Badge>
                    </Group>
                  }
                  leftSection={<LuShieldCheck />}
                  aria-label="Ops"
                />
              </Tooltip>
            ) : null}
            <NavLink
              component="button"
              visibleFrom="sm"
              label="Collapse"
              leftSection={rail ? <LuChevronsRight /> : <LuChevronsLeft />}
              onClick={() => setRail(!rail)}
              aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
            />
          </Stack>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main className="kv2-shell-main">
        <div className="kv2-mock-banner">
          <StatusBadge tone="caution" size="xs">
            Preview
          </StatusBadge>
          v2 design preview · sample data only
        </div>
        {children}
      </AppShell.Main>

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
