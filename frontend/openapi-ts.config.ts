import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "./openapi/app.json",
  output: "./src/shared/api/generated",
  plugins: ["@hey-api/typescript", "zod"],
});
