import api from "@/lib/api";

// ── Dashboard types ──────────────────────────────────────────
export interface ClientActiveSubscription {
  id: string;
  service_name: string;
  service_icon: string | null;
  plan_name: string;
  plan_price: string | null;
  status: string;
  starts_at: string;
  expires_at: string;
}

export interface ClientDashboardData {
  message: string;
  id: string;
  full_name: string;
  username: string;
  phone: string | null;
  tenant_id: string;
  tenant_name: string;
  client_prefix: string;
  is_active: boolean;
  subscriptions: ClientActiveSubscription[];
  currency: { code: string; symbol: string; minor_units: number } | null;
}

// ── Profile types (from /me) ────────────────────────────────
export interface ClientProfile {
  role: string;
  username: string;
  name: string | null;
  full_name: string | null;
  tenant_id: string | null;
  tenant_name: string | null;
  client_prefix: string | null;
  locale: string | null;
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
}

export interface PasswordChange {
  old_password: string;
  new_password: string;
}

// ── API calls ───────────────────────────────────────────────
export async function fetchClientDashboard(): Promise<ClientDashboardData> {
  const { data } = await api.get("/dashboard");
  return data;
}

export async function getProfile(): Promise<ClientProfile> {
  const { data } = await api.get("/me");
  return data;
}

export async function updateProfile(payload: ProfileUpdate): Promise<ClientProfile> {
  const { data } = await api.put("/me", payload);
  return data;
}

export async function changePassword(payload: PasswordChange): Promise<void> {
  await api.put("/me/password", payload);
}
