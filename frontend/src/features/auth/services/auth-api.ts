import api from "@/lib/api";

export interface LoginResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    username: string
    role: string
    tenant_id?: string
  }
}

export async function loginApi(
  username: string,
  password: string
): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>("/auth/login", {
    username,
    password,
  })
  return res.data
}

export async function logoutApi(): Promise<void> {
  await api.post("/auth/logout")
}

export async function switchTenantApi(
  tenantId: string
): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>("/auth/switch-tenant", {
    tenant_id: tenantId,
  })
  return res.data
}
