import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { createFileRoute, Outlet } from "@tanstack/react-router";

import { EmptyState, AppLink } from "../v2/components";
import { V2ThemeScope } from "../v2/theme/V2ThemeScope";
import "../v2/theme/v2.css";

export const Route = createFileRoute("/v2")({
  component: V2Layout,
  notFoundComponent: V2NotFound,
});

function V2Layout() {
  return (
    <V2ThemeScope>
      <ModalsProvider>
        <Outlet />
        <Notifications position="bottom-right" limit={3} />
      </ModalsProvider>
    </V2ThemeScope>
  );
}

function V2NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="This v2 preview page doesn't exist."
      action={<AppLink href="/v2/">Back to the v2 index</AppLink>}
    />
  );
}
