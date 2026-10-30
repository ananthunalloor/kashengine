import { createFileRoute } from "@tanstack/react-router";

import { PublicNotFoundPage } from "../v2/pages/PublicExtras";

export const Route = createFileRoute("/v2/public/$")({ component: PublicNotFoundPage });
