import api from "@/lib/api";

export type TenantPlan = "starter" | "pro";

export interface UserInfo {
  id: string
  role: string
  username: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
  active_tenant_id: string | null
  tenant_plan: TenantPlan | null
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

export async function switchTenantApi(
  tenantId: string | null
): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/switch-tenant", {
    tenant_id: tenantId,
  });
  return res.data;
}
