import { createFileRoute, Outlet } from "@tanstack/react-router";

import { V2Shell } from "../v2/components";

export const Route = createFileRoute("/v2/_app")({
  component: () => (
    <V2Shell>
      <Outlet />
    </V2Shell>
  ),
});
