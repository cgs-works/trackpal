import { createFileRoute } from "@tanstack/react-router";
import { SubscriptionsPage } from "@/features/admin/components/subscriptions-page";
import { PlanRouteGate } from "@/features/admin/components/plan-route-gate";

export const Route = createFileRoute("/admin/subscriptions")({
  component: () => (
    <PlanRouteGate>
      <SubscriptionsPage />
    </PlanRouteGate>
  ),
});
