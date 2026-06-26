import { createFileRoute } from "@tanstack/react-router";
import { ClientsPage } from "@/features/admin/components/clients-page";
import { PlanRouteGate } from "@/features/admin/components/plan-route-gate";

export const Route = createFileRoute("/admin/clients")({
  component: () => (
    <PlanRouteGate>
      <ClientsPage />
    </PlanRouteGate>
  ),
});
