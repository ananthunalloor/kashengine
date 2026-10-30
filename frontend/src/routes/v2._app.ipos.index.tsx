import { createFileRoute } from "@tanstack/react-router";

import { IposPage } from "../v2/pages/Ipos";

export const Route = createFileRoute("/v2/_app/ipos/")({
  component: IposPage,
});
