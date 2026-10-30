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
    ],
  },
];

export function GalleryPage() {
  return (
    <Page>
      <PageHeader
        title="v2 preview gallery"
        meta={<StatusBadge tone="caution">Sample data</StatusBadge>}
        description="Every page of the redesigned UI, filled with fictional placeholder data. Ops pages come later."
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
        <Text size="xs" c="dimmed">
          Ops (staff) pages — jobs, runs, logs, users and more — will be added in a later preview.
        </Text>
      </Stack>
    </Page>
  );
}
