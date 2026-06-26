import type { ReactNode } from "react";
import { useAuthStore } from "@/store/auth";
import { NotFoundPage } from "./not-found-page";

export function PlanRouteGate({ children }: { children: ReactNode }) {
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";

  if (isStarterTenantAdmin && !isMasterSupportContext) {
    return <NotFoundPage />;
  }

  return <>{children}</>;
}
