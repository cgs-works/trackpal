import api from "@/lib/api";

// ── Profile ───────────────────────────────────────────────────
export interface Profile {
  role: string;
  username: string;
  name: string | null;
  full_name: string | null;
  tenant_id: string | null;
  tenant_name: string | null;
  client_prefix: string | null;
  locale: string | null;
  timezone: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdate {
  full_name?: string;
  email?: string;
  phone?: string;
  name?: string;
}

export interface PasswordChange {
  old_password: string;
  new_password: string;
}

// ── Mailbox ───────────────────────────────────────────────────
export interface Mailbox {
  id: string;
  tenant_id: string;
  mailbox_email: string;
  status: string;
  last_connection_test_at: string | null;
  last_connection_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface GmailAppPasswordConnect {
  mailbox_email: string;
  app_password: string;
}

// ── Code Services ─────────────────────────────────────────────
export interface TenantCodeService {
  service_key: string;
  label: string;
  is_selected: boolean;
  is_globally_active: boolean;
}

export interface TenantCodeServiceResponse {
  tenant_id: string;
  services: TenantCodeService[];
}

// ── API calls ─────────────────────────────────────────────────

// Profile
export async function getProfile(): Promise<Profile> {
  const { data } = await api.get("/me");
  return data;
}

export async function updateProfile(payload: ProfileUpdate): Promise<Profile> {
  const { data } = await api.put("/me", payload);
  return data;
}

export async function changePassword(payload: PasswordChange): Promise<void> {
  await api.put("/me/password", payload);
}

// Master Support Context: read/update the selected tenant's profile
export async function getTenantProfile(): Promise<Profile> {
  const { data } = await api.get("/me/tenant-profile");
  return data;
}

export async function updateTenantProfile(payload: ProfileUpdate): Promise<Profile> {
  const { data } = await api.put("/me/tenant-profile", payload);
  return data;
}

// ── Tenant Settings ───────────────────────────────────────────
export interface TenantSettings {
  tenant_id: string;
  locale: string;
  timezone: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantSettingsUpdate {
  locale?: string;
  timezone?: string;
}

export interface TimezoneOption {
  value: string;
  label: string;
  group: string;
}

export async function getTenantSettings(): Promise<TenantSettings> {
  const { data } = await api.get("/tenant-settings");
  return data;
}

export async function updateTenantSettings(
  payload: TenantSettingsUpdate
): Promise<TenantSettings> {
  const { data } = await api.put("/tenant-settings", payload);
  return data;
}

export async function getTimezones(): Promise<TimezoneOption[]> {
  const { data } = await api.get("/tenant-settings/timezones");
  return data;
}

// Mailbox
export async function getMailbox(): Promise<Mailbox | null> {
  try {
    const { data } = await api.get("/tenant/mailbox/");
    return data;
  } catch (err: any) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
}

export async function connectGmail(payload: GmailAppPasswordConnect): Promise<Mailbox> {
  const { data } = await api.put("/tenant/mailbox/", payload);
  return data;
}

export async function testMailbox(): Promise<{
  success: boolean;
  message: string;
}> {
  const { data } = await api.post("/tenant/mailbox/test");
  return data;
}

export async function disconnectMailbox(): Promise<void> {
  await api.post("/tenant/mailbox/disconnect");
}

// Code Services
export async function getTenantCodeServices(): Promise<TenantCodeServiceResponse> {
  const { data } = await api.get("/code-services/tenants/current");
  return data;
}

export async function updateTenantCodeServices(
  serviceKeys: string[]
): Promise<TenantCodeServiceResponse> {
  const { data } = await api.put("/code-services/tenants/current", {
    service_keys: serviceKeys,
  });
  return data;
}

// ── Tenant self-service deletion ────────────────────────────────

export interface DeleteAccountRequest {
  password: string;
  destructive_word: string;
}

export interface DeleteAccountResponse {
  success: boolean;
}

export async function deleteAccount(
  payload: DeleteAccountRequest
): Promise<DeleteAccountResponse> {
  const { data } = await api.post("/me/delete-account", payload);
  return data;
}


// ── Tenant Data Export ────────────────────────────────────────
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
  attempt: number;
  max_attempts: number;
  /** @deprecated Use `attempts` instead */
  attempts?: number;
  /** When the job transitioned to failed (for 72h cleanup display) */
  failed_at?: string | null;
  /** When the 24h cooldown expires (ISO 8601) */
  cooldown_until?: string | null;
  /** Role of the actor who requested the job: "tenant" or "master" */
  actor_role?: string | null;
  /** ID of the job this one replaces (if any) */
  replaced_job_id?: string | null;
  /** ID of the job that replaces this one (if any) */
  replacement_job_id?: string | null;
  /** Previous ready artifact details, available if a replacement is pending */
  previous_ready?: PreviousReadyInfo | null;
}

export interface ExportDownloadResponse {
  download_url: string;
  expires_in: number;
}

export interface ExportCancelResponse {
  status: string;
  id: string;
}

export async function requestExport(): Promise<ExportJobStatusResponse> {
  const { data } = await api.post("/me/export");
  return data;
}

export async function getExportStatus(): Promise<ExportJobStatusResponse | null> {
  try {
    const { data } = await api.get("/me/export");
    return data;
  } catch (err: any) {
    if (err?.response?.status === 204) return null;
    throw err;
  }
}

export async function getExportDownloadUrl(): Promise<ExportDownloadResponse> {
  const { data } = await api.get("/me/export/download");
  return data;
}

export async function cancelExport(): Promise<ExportCancelResponse> {
  const { data } = await api.post("/me/export/cancel");
  return data;
}

// ── Public API Key ────────────────────────────────────────────
export interface PublicApiKeyConfig {
  tenant_id: string;
  api_key: string;
  allowed_origins: string[];
  created_at: string;
  updated_at: string;
}

export async function getPublicApiKey(): Promise<PublicApiKeyConfig | null> {
  const { data } = await api.get("/public-api-key");
  return data;
}

export async function savePublicApiKeyOrigins(
  allowedOrigins: string[],
): Promise<PublicApiKeyConfig> {
  const { data } = await api.put("/public-api-key", {
    allowed_origins: allowedOrigins,
  });
  return data;
}

export async function regeneratePublicApiKey(): Promise<PublicApiKeyConfig> {
  const { data } = await api.post("/public-api-key/regenerate");
  return data;
}

export async function revokePublicApiKey(): Promise<void> {
  await api.delete("/public-api-key");
}
