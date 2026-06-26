import { createFileRoute } from "@tanstack/react-router";
import { CatalogPage } from "@/features/admin/components/catalog-page";
import { PlanRouteGate } from "@/features/admin/components/plan-route-gate";

export const Route = createFileRoute("/admin/catalog")({
  component: () => (
    <PlanRouteGate>
      <CatalogPage />
    </PlanRouteGate>
  ),
});
