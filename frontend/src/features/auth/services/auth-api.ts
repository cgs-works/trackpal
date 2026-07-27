import api from "@/lib/api";

export type TenantPlan = "starter" | "pro";
export type DemoTenantStatus = "pending" | "active" | "expired";

export interface UserInfo {
  id: string;
  role: string;
  username: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserInfo;
  active_tenant_id: string | null;
  tenant_plan: TenantPlan | null;
  is_demo: boolean;
  demo_tenant_id: string | null;
  demo_name: string | null;
  demo_status: DemoTenantStatus | null;
  demo_activated_at: string | null;
  demo_expires_at: string | null;
  demo_credentials_version: number | null;
  server_time: string;
}

export interface DemoHeartbeatResponse {
  is_demo: boolean;
  demo_tenant_id: string | null;
  demo_name: string | null;
  tenant_plan: TenantPlan | null;
  demo_status: DemoTenantStatus | null;
  demo_activated_at: string | null;
  demo_expires_at: string | null;
  demo_credentials_version: number | null;
  server_time: string;
}

export type AuthFailureCode = "demo_ended" | "demo_credentials_replaced";

function getErrorDetail(error: unknown): unknown {
  if (!error || typeof error !== "object" || !("response" in error)) {
    return undefined;
  }
  const response = error.response;
  if (!response || typeof response !== "object" || !("data" in response)) {
    return undefined;
  }
  const data = response.data;
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return undefined;
  }
  return data.detail;
}

export function getAuthFailureCode(error: unknown): AuthFailureCode | null {
  const detail = getErrorDetail(error);
  return detail === "demo_ended" || detail === "demo_credentials_replaced"
    ? detail
    : null;
}

export async function loginApi(
  username: string,
  password: string
): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/login", {
    username,
    password,
  });
  return res.data;
}

export async function logoutApi(refreshToken: string | null): Promise<void> {
  await api.post("/auth/logout", { refresh_token: refreshToken });
}

export async function refreshApi(refreshToken: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function heartbeatApi(): Promise<DemoHeartbeatResponse> {
  const { data } = await api.post<DemoHeartbeatResponse>("/auth/heartbeat");
  return data;
}

export async function switchTenantApi(
  tenantId: string | null
): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/switch-tenant", {
    tenant_id: tenantId,
  });
  return res.data;
}
