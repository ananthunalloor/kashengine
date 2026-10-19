import { Stack, Text, Title } from "@mantine/core";
import { createFileRoute } from "@tanstack/react-router";
import { LuArrowUpRight, LuChartNoAxesCombined, LuSparkles } from "react-icons/lu";

import { usePageTitle } from "../shared/ui/usePageTitle";

function AppHome() {
  usePageTitle("React preview");
  const { session } = Route.useRouteContext();
  const previews = new Set([
    "/dashboard/",
    "/account/",
    "/reports/",
    "/news/",
    "/ipos/",
    "/markets/",
    "/companies/",
    "/delivery/",
    "/ops/",
  ]);
  return (
    <Stack gap="xl">
      <header>
        <Text className="app-eyebrow" mb="sm">
          <LuSparkles aria-hidden="true" /> Your intelligence workspace
        </Text>
        <Title order={1} tabIndex={-1}>
          React preview
        </Title>
        <Text maw={640} c="dimmed" mt="sm">
          Your account's available sections are in the navigation. Today, Reports, News, IPOs,
          Markets, Companies, Delivery, and Account now have React previews. Staff also have the
          complete Operations workspace; administrative actions retain their existing superuser
          permissions. Original Django pages remain available for comparison.
        </Text>
      </header>
      <div className="workspace-welcome">
        <div>
          <span className="workspace-icon">
            <LuChartNoAxesCombined aria-hidden="true" />
          </span>
          <Title order={2} mt="md">
            Less noise. More perspective.
          </Title>
          <Text c="dimmed" mt="sm">
            Explore the stories, companies, and signals shaping the market. Your available sections
            are ready below.
          </Text>
        </div>
        <span className="welcome-decoration" aria-hidden="true">
          <LuChartNoAxesCombined />
        </span>
      </div>
      <div className="workspace-links">
        {session.navigation
          .filter((item) => previews.has(item.url))
          .map((item) => (
            <a key={item.url} href={`/app${item.url}`}>
              <span>{item.label}</span>
              <LuArrowUpRight aria-hidden="true" />
            </a>
          ))}
        {session.is_staff && (
          <a href="/app/ops/runs/">
            <span>Ops task runs</span>
            <LuArrowUpRight aria-hidden="true" />
          </a>
        )}
        {session.is_staff && (
          <a href="/app/ops/audit/">
            <span>Ops audit trail</span>
            <LuArrowUpRight aria-hidden="true" />
          </a>
        )}
      </div>
    </Stack>
  );
}

export const Route = createFileRoute("/")({ component: AppHome });
