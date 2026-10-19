import "./app/validation";
import "./styles/app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ThemeProvider } from "./app/ThemeProvider";
import { PublicPage, publicPageSchema } from "./features/public/PublicPage";

const root = document.getElementById("root");
const bootstrap = document.getElementById("public-preview");
if (!root || !bootstrap?.textContent) throw new Error("Missing public page presentation data.");
const data = publicPageSchema.parse(JSON.parse(bootstrap.textContent));

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <PublicPage data={data} />
    </ThemeProvider>
  </StrictMode>,
);
