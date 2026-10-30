import { createFileRoute, Outlet } from "@tanstack/react-router";

import { PublicShell } from "../v2/components";

export const Route = createFileRoute("/v2/public")({
  component: () => (
    <PublicShell>
      <Outlet />
    </PublicShell>
  ),
});
