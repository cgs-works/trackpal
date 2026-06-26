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
  provider: string;
  auth_method: string;
  status: string;
  oauth_provider_user_id: string | null;
  oauth_provider_email: string | null;
  imap_host: string | null;
  imap_port: number | null;
  imap_ssl: boolean | null;
  last_connection_test_at: string | null;
  last_connection_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MailboxConfigUpdate {
  provider: "google" | "microsoft" | "imap_custom";
  mailbox_email: string;
  imap_host?: string;
  imap_port?: number;
  imap_ssl?: boolean;
  imap_password?: string;
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

export async function upsertMailbox(
  payload: MailboxConfigUpdate
): Promise<Mailbox> {
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

export async function startOAuth(
  provider: "google" | "microsoft"
): Promise<{ auth_url: string; state: string }> {
  const { data } = await api.post(
    `/tenant/mailbox/oauth/${provider}/start`
  );
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
