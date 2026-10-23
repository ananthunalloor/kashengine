import "./app/validation";
import "./styles/app.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { queryClient } from "./app/query-client";
import { router } from "./app/router";
import { ThemeProvider } from "./app/ThemeProvider";
import { SkipLink } from "./shared/ui/SkipLink";
import { Notifications } from "./shared/ui/Notifications";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Could not find the React root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <SkipLink />
    <ThemeProvider>
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
