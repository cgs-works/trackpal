import api from "@/lib/api";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export interface Tenant {
  id: string
  full_name: string
  client_prefix: string
  email: string | null
  phone: string | null
  evolution_instance_name: string | null
  is_active: boolean
  username: string
  created_at: string
  plan: TenantPlan
}

export interface TenantMeta {
  total: number
  active: number
  inactive: number
}

export interface TenantListResponse {
  data: Tenant[]
  meta: TenantMeta
}

export interface CodeService {
  service_key: string
  label: string
  is_active: boolean
}

export async function fetchTenants(): Promise<TenantListResponse> {
  const res = await api.get<TenantListResponse>("/tenants")
  return res.data
}

export async function createTenant(
  data: Record<string, unknown>
): Promise<{ data: Tenant; generated_password?: string }> {
  const res = await api.post("/tenants", data)
  return res.data
}

export async function updateTenant(
  id: string,
  data: Record<string, unknown>
): Promise<void> {
  await api.put(`/tenants/${id}`, data)
}

export async function deleteTenant(id: string): Promise<void> {
  await api.delete(`/tenants/${id}`)
}

export async function activateTenant(id: string): Promise<void> {
  await api.patch(`/tenants/${id}/activate`)
}

export async function deactivateTenant(id: string): Promise<void> {
  await api.patch(`/tenants/${id}/deactivate`)
}

export async function fetchCodeServices(): Promise<CodeService[]> {
  const res = await api.get<{ services: CodeService[] }>("/code-services/global")
  return res.data.services || []
}

export async function saveCodeServices(
  services: Record<string, boolean>
): Promise<void> {
  await api.put("/code-services/global", { services })
}
