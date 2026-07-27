import api from "@/lib/api";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export type DemoTenantStatus = "pending" | "active" | "expired";

export interface DemoTenant {
  id: string;
  name: string;
  plan: TenantPlan;
  status: DemoTenantStatus;
  username: string;
  created_at: string;
  demo_activated_at: string | null;
  demo_expires_at: string | null;
  server_time: string;
  remaining_seconds: number | null;
}

export interface DemoTenantCredentials extends DemoTenant {
  plain_password: string;
}

export async function fetchDemos(): Promise<DemoTenant[]> {
  const { data } = await api.get<DemoTenant[]>("/demos/");
  return data;
}

export async function createDemo(payload: {
  name: string;
  plan: TenantPlan;
}): Promise<DemoTenantCredentials> {
  const { data } = await api.post<DemoTenantCredentials>("/demos/", payload);
  return data;
}

export async function replaceDemoCredentials(
  demoId: string,
): Promise<DemoTenantCredentials> {
  const { data } = await api.post<DemoTenantCredentials>(
    `/demos/${demoId}/credentials`,
  );
  return data;
}

export async function deleteDemo(demoId: string): Promise<void> {
  await api.delete(`/demos/${demoId}`);
}
