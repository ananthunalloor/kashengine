import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ThemeProvider } from "../../app/ThemeProvider";
import { routeTree } from "../../routeTree.gen";
import { PublicPage, publicPageSchema } from "../../features/public/PublicPage";
import { session } from "../../test/session";

it("renders the public 404 with safe recovery links and no session fetch", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <ThemeProvider>
      <PublicPage
        data={publicPageSchema.parse({ page: "not-found", authenticated: false, csrf: "test" })}
      />
    </ThemeProvider>,
  );
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Page not found");
  expect(screen.getByText("404")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to home" })).toHaveAttribute("href", "/app/landing/");
  expect(screen.getByRole("link", { name: "Open dashboard" })).toHaveAttribute(
    "href",
    "/app/dashboard/",
  );
  expect(document.title).toBe("Page not found | Kash Engine");
  expect(fetch).not.toHaveBeenCalled();
});

it("catches unmatched React navigation without replacing the application shell", async () => {
  vi.stubGlobal("scrollTo", vi.fn());
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(session), {
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  const router = createRouter({
    routeTree,
    basepath: "/app",
    history: createMemoryHistory({ initialEntries: ["/app/not-a-real-page/"] }),
    context: { queryClient: client },
  });
  const view = render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Page not found");
  expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/not-a-real-page/");
  view.unmount();
  client.clear();
});
