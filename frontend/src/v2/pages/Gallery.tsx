import { Card, Group, SimpleGrid, Stack, Text, ThemeIcon } from "@mantine/core";
import type { IconType } from "react-icons";
import {
  LuArrowRight,
  LuBuilding,
  LuBuilding2,
  LuChartCandlestick,
  LuFileText,
  LuGlobe,
  LuLayoutDashboard,
  LuLogIn,
  LuNewspaper,
  LuPalette,
  LuRocket,
  LuSend,
  LuSettings2,
  LuShieldCheck,
  LuUser,
  LuUserPlus,
} from "react-icons/lu";

import { AppLink, Page, PageHeader, Panel, StatusBadge } from "../components";
import { companies } from "../mock/data";

type Entry = { label: string; href: string; description: string; icon: IconType };

const groups: { title: string; info: string; entries: Entry[] }[] = [
  {
    title: "App pages",
    info: "Signed-in pages rendered inside the v2 shell (header, sidebar, sample-data banner).",
    entries: [
      {
        label: "Today",
        href: "/v2/today/",
        description: "Morning overview: outlook, indices, stocks to watch, news.",
        icon: LuLayoutDashboard,
      },
      {
        label: "Reports",
        href: "/v2/reports/",
        description: "Archive of daily briefs with search and filters.",
        icon: LuFileText,
      },
      {
        label: "Report detail",
        href: "/v2/reports/2026-01-12/",
        description: "A single daily brief with sections and delivery info.",
        icon: LuFileText,
      },
      {
        label: "News",
        href: "/v2/news/",
        description: "Scored news feed with sentiment filters.",
        icon: LuNewspaper,
      },
      {
        label: "IPOs",
        href: "/v2/ipos/",
        description: "Open, upcoming and listed IPOs with verdicts.",
        icon: LuRocket,
      },
      {
        label: "IPO detail",
        href: "/v2/ipos/sample-ipo/",
        description: "Issue details, subscription and scoring for one IPO.",
        icon: LuRocket,
      },
      {
        label: "Markets",
        href: "/v2/markets/",
        description: "Indices, breadth, global cues and prediction history.",
        icon: LuChartCandlestick,
      },
      {
        label: "Live quotes",
        href: "/v2/markets/live/",
        description: "Current sample quotes and feed freshness.",
        icon: LuChartCandlestick,
      },
      {
        label: "Instruments",
        href: "/v2/markets/instruments/",
        description: "Search the mock market instrument directory.",
        icon: LuChartCandlestick,
      },
      {
        label: "Companies",
        href: "/v2/companies/",
        description: "Searchable company list with signals and delivery %.",
        icon: LuBuilding2,
      },
      {
        label: "Company detail",
        href: `/v2/companies/${companies[0].id}/`,
        description: "Price chart, fundamentals, news and delivery for one company.",
        icon: LuBuilding,
      },
      {
        label: "Delivery",
        href: "/v2/delivery/",
        description: "Channels and schedule for receiving the daily brief.",
        icon: LuSend,
      },
      {
        label: "Account",
        href: "/v2/account/",
        description: "Profile, security, features and subscription.",
        icon: LuUser,
      },
      {
        label: "Design system",
        href: "/v2/design-system/",
        description: "Living reference of tokens and shared components.",
        icon: LuPalette,
      },
    ],
  },
  {
    title: "Public",
    info: "Signed-out pages rendered inside the public header and footer.",
    entries: [
      {
        label: "Landing",
        href: "/v2/public/",
        description: "Product overview and call to sign up.",
        icon: LuGlobe,
      },
      {
        label: "Log in",
        href: "/v2/public/login/",
        description: "Email and password sign-in.",
        icon: LuLogIn,
      },
      {
        label: "Sign up",
        href: "/v2/public/signup/",
        description: "Invite-based account creation.",
        icon: LuUserPlus,
      },
      {
        label: "Sign-up complete",
        href: "/v2/public/signup-complete/",
        description: "Preview of the account request confirmation state.",
        icon: LuUserPlus,
      },
      {
        label: "Email verification",
        href: "/v2/public/verify-email/sample-token/",
        description: "Preview of the verification result state.",
        icon: LuUserPlus,
      },
      {
        label: "Access unavailable",
        href: "/v2/public/access/",
        description: "Locked or unavailable feature state.",
        icon: LuUser,
      },
      {
        label: "Legal",
        href: "/v2/public/legal/",
        description: "Placeholder terms and privacy disclosures.",
        icon: LuFileText,
      },
      {
        label: "Not found",
        href: "/v2/public/not-found/",
        description: "Public 404 state for unknown preview pages.",
        icon: LuGlobe,
      },
    ],
  },
  {
    title: "Operations (staff)",
    info: "Mock versions of the original staff-only Ops routes and the operations design concepts.",
    entries: [
      {
        label: "Overview",
        href: "/v2/ops/",
        description: "System health, sample service checks and recent activity.",
        icon: LuLayoutDashboard,
      },
      {
        label: "Jobs & queues",
        href: "/v2/ops/jobs/",
        description: "Job registry, queue states and sample run actions.",
        icon: LuSettings2,
      },
      {
        label: "Task runs",
        href: "/v2/ops/runs/",
        description: "Run history and a sample task detail.",
        icon: LuSettings2,
      },
      {
        label: "Logs",
        href: "/v2/ops/logs/",
        description: "Sample worker log stream and filters.",
        icon: LuSettings2,
      },
      {
        label: "SMTP queue & relay",
        href: "/v2/ops/smtp/",
        description: "Mock outbound queue and safe failover controls.",
        icon: LuSettings2,
      },
      {
        label: "Metrics",
        href: "/v2/ops/metrics/",
        description: "Placeholder telemetry for workers and queues.",
        icon: LuSettings2,
      },
      {
        label: "Schedule",
        href: "/v2/ops/schedule/",
        description: "Recurring task schedule and edit states.",
        icon: LuSettings2,
      },
      {
        label: "Users & access",
        href: "/v2/ops/users/",
        description: "Mock accounts, entitlements and user detail.",
        icon: LuUser,
      },
      {
        label: "Invite codes",
        href: "/v2/ops/invites/",
        description: "Create and review fictional invite tokens.",
        icon: LuUserPlus,
      },
      {
        label: "Subscriptions",
        href: "/v2/ops/subscriptions/",
        description: "Sample subscription states and renewals.",
        icon: LuUser,
      },
      {
        label: "Logins & lockouts",
        href: "/v2/ops/logins/",
        description: "Mock sessions and sign-in activity.",
        icon: LuShieldCheck,
      },
      {
        label: "Audit trail",
        href: "/v2/ops/audit/",
        description: "Sample append-only admin activity.",
        icon: LuFileText,
      },
      {
        label: "Feeds",
        href: "/v2/ops/feeds/",
        description: "Sample ingestion source health and status.",
        icon: LuSettings2,
      },
      {
        label: "Instrument master",
        href: "/v2/ops/instruments/",
        description: "Manageable mock market instrument list.",
        icon: LuChartCandlestick,
      },
      {
        label: "Config & settings",
        href: "/v2/ops/config/",
        description: "Settings groups and safe placeholder values.",
        icon: LuSettings2,
      },
      {
        label: "Backups",
        href: "/v2/ops/backups/",
        description: "Sample backup and recovery status.",
        icon: LuSettings2,
      },
    ],
  },
];

export function GalleryPage() {
  return (
    <Page>
      <PageHeader
        title="v2 preview gallery"
        meta={<StatusBadge tone="caution">Sample data</StatusBadge>}
        description="The redesigned product and operations pages, filled with fictional placeholder data."
      />
      <Stack gap={16}>
        {groups.map((group) => (
          <Panel
            key={group.title}
            title={group.title}
            info={group.info}
            actions={
              <Text size="xs" c="dimmed">
                {group.entries.length} pages
              </Text>
            }
          >
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3, xl: 4 }} spacing={12}>
              {group.entries.map((entry) => (
                <Card
                  key={entry.href}
                  component={AppLink}
                  href={entry.href}
                  padding="sm"
                  style={{ color: "inherit", textDecoration: "none" }}
                >
                  <Group gap={10} wrap="nowrap" align="flex-start">
                    <ThemeIcon variant="light" color="indigo" size={28} radius="xs">
                      <entry.icon size={16} />
                    </ThemeIcon>
                    <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
                      <Group justify="space-between" wrap="nowrap" gap={4}>
                        <Text size="sm" fw={600}>
                          {entry.label}
                        </Text>
                        <LuArrowRight size={12} />
                      </Group>
                      <Text size="xs" c="dimmed">
                        {entry.description}
                      </Text>
                      <Text size="xs" className="kv2-mono" c="dimmed" truncate>
                        {entry.href}
                      </Text>
                    </Stack>
                  </Group>
                </Card>
              ))}
            </SimpleGrid>
          </Panel>
        ))}
      </Stack>
    </Page>
  );
}
