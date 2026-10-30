import { createFileRoute } from "@tanstack/react-router";

import { AccessPage } from "../v2/pages/PublicExtras";

export const Route = createFileRoute("/v2/public/access")({ component: AccessPage });
