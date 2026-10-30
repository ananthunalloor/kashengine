import { createFileRoute } from "@tanstack/react-router";

import { LegalPage } from "../v2/pages/PublicExtras";

export const Route = createFileRoute("/v2/public/legal")({ component: LegalPage });
