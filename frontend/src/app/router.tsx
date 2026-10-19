import { createRouter } from "@tanstack/react-router";

import { routeTree } from "../routeTree.gen";
import { queryClient } from "./query-client";

export const router = createRouter({
  routeTree,
  basepath: "/",
  trailingSlash: "always",
  defaultPreload: "intent",
  scrollRestoration: true,
  context: { queryClient },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
