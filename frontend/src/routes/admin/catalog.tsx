import { createFileRoute } from "@tanstack/react-router";
import { CatalogPage } from "@/features/admin/components/catalog-page";

export const Route = createFileRoute("/admin/catalog")({
  component: CatalogPage,
});
