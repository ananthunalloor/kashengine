import { createFileRoute } from "@tanstack/react-router";

import { GalleryPage } from "../v2/pages/Gallery";

export const Route = createFileRoute("/v2/_app/")({
  component: GalleryPage,
});
