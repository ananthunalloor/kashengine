import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/app/",
  plugins: [
    tanstackRouter({
      autoCodeSplitting: true,
      routesDirectory: "./src/routes",
      generatedRouteTree: "./src/routeTree.gen.ts",
    }),
    tailwindcss(),
    react(),
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: {
      origin: ["http://localhost:8000", "https://localhost"],
    },
  },
  build: {
    manifest: "manifest.json",
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: "./index.html",
        app: "./src/main.tsx",
      },
    },
  },
});
