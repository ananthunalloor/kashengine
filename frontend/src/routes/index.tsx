import { createFileRoute } from "@tanstack/react-router";

import { Landing } from "../features/public/PublicPage";
import { usePageTitle } from "../shared/ui/usePageTitle";

function Home() {
  usePageTitle("Less noise. More perspective.");
  return <Landing authenticated />;
}

export const Route = createFileRoute("/")({ component: Home });
