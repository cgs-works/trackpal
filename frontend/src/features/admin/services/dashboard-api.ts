import api from "@/lib/api";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export interface TenantDashboardResponse {
  message: string;
  full_name: string;
  tenant_plan: TenantPlan;
  mailbox_status: string;
  enabled_code_services: string[];
  access_control_count: number;
  active_clients: number | null;
  catalog_services: number | null;
  active_subscriptions: number | null;
  subscriptions_expiring_soon: number | null;
  reminders_enabled?: boolean | null;
}

export async function getTenantDashboard(): Promise<TenantDashboardResponse> {
  const { data } = await api.get("/dashboard");
  return data;
}
