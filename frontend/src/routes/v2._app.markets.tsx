import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/v2/_app/markets")({
  component: () => <Outlet />,
});
