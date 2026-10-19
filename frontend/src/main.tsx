import "./styles/app.css";

import { MantineProvider } from "@mantine/core";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { queryClient } from "./app/query-client";
import { router } from "./app/router";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Could not find the React root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <MantineProvider defaultColorScheme="auto" theme={{ respectReducedMotion: true }}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
