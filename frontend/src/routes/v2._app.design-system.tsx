import { createFileRoute } from "@tanstack/react-router";

import { DesignSystemPage } from "../v2/pages/DesignSystem";

export const Route = createFileRoute("/v2/_app/design-system")({
  component: DesignSystemPage,
});
