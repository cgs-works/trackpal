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

// ── Master Tenant Data Export ─────────────────────────────────

export type ExportJobStatus = "pending" | "processing" | "ready" | "failed" | "cancelled";

export interface PreviousReadyInfo {
  id: string;
  ready_at: string | null;
  artifact_size_bytes: number | null;
  expires_at: string | null;
}

export interface ExportJobStatusResponse {
  id: string;
  tenant_id?: string;
  status: ExportJobStatus;
  created_at: string;
  ready_at: string | null;
  expires_at: string | null;
  artifact_size_bytes: number | null;
  error_code: string | null;
  error_detail: string | null;
  attempts?: number;
  max_attempts: number;
  failed_at?: string | null;
  cooldown_until?: string | null;
  actor_role?: string | null;
  replaced_job_id?: string | null;
  replacement_job_id?: string | null;
  previous_ready?: PreviousReadyInfo | null;
}

export interface ExportDownloadResponse {
  download_url: string;
  expires_in: number;
}

export async function masterRequestExport(
  tenantId: string,
  password: string
): Promise<ExportJobStatusResponse> {
  const { data } = await api.post(`/tenants/${tenantId}/export`, { password });
  return data;
}

export async function masterGetExportStatus(
  tenantId: string
): Promise<ExportJobStatusResponse | null> {
  try {
    const { data } = await api.get(`/tenants/${tenantId}/export`);
    return data;
  } catch (err: any) {
    if (err?.response?.status === 204) return null;
    throw err;
  }
}

export async function masterCancelExport(
  tenantId: string
): Promise<{ status: string; id: string }> {
  const { data } = await api.post(`/tenants/${tenantId}/export/cancel`);
  return data;
}

export async function masterGetExportDownloadUrl(
  tenantId: string
): Promise<ExportDownloadResponse> {
  const { data } = await api.get(`/tenants/${tenantId}/export/download`);
  return data;
}
