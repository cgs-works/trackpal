import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────
export interface Subscription {
  id: string;
  tenant_id: string;
  client_id: string;
  service_id: string;
  plan_id: string;
  streaming_email: string;
  profile_name: string | null;
  duration_type: string;
  starts_at: string;
  expires_at: string;
  cancelled_at: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  has_password: boolean;
  has_pin: boolean;
}

export interface SubscriptionCreate {
  client_id: string;
  service_id: string;
  plan_id: string;
  streaming_email: string;
  streaming_password?: string;
  profile_name?: string;
  profile_pin?: string;
  duration_type: string;
  starts_at: string;
  expires_at?: string;
}

export interface SubscriptionUpdate {
  client_id?: string;
  service_id?: string;
  plan_id?: string;
  streaming_email?: string;
  streaming_password?: string;
  profile_name?: string;
  profile_pin?: string;
  duration_type?: string;
  starts_at?: string;
  expires_at?: string;
}

export interface RevealCredentials {
  streaming_password: string | null;
  profile_pin: string | null;
}

export interface SubscriptionFilters {
  status?: string;
  client_id?: string;
  service_id?: string;
  quick_filter?: string;
}

// ── API calls ─────────────────────────────────────────────────
export async function listSubscriptions(
  filters: SubscriptionFilters = {}
): Promise<Subscription[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.client_id) params.set("client_id", filters.client_id);
  if (filters.service_id) params.set("service_id", filters.service_id);
  if (filters.quick_filter) params.set("quick_filter", filters.quick_filter);
  const qs = params.toString();
  const { data } = await api.get(`/subscriptions${qs ? `?${qs}` : ""}`);
  return data;
}

export async function getSubscription(
  id: string
): Promise<Subscription> {
  const { data } = await api.get(`/subscriptions/${id}`);
  return data;
}

export async function createSubscription(
  payload: SubscriptionCreate
): Promise<Subscription> {
  const { data } = await api.post("/subscriptions", payload);
  return data;
}

export async function updateSubscription(
  id: string,
  payload: SubscriptionUpdate
): Promise<Subscription> {
  const { data } = await api.put(`/subscriptions/${id}`, payload);
  return data;
}

export async function revealCredentials(
  id: string
): Promise<RevealCredentials> {
  const { data } = await api.get(`/subscriptions/${id}/reveal`);
  return data;
}

// ── Lifecycle mutations ──────────────────────────────────────
export async function cancelSubscription(
  id: string
): Promise<Subscription> {
  const { data } = await api.post(`/subscriptions/${id}/cancel`);
  return data;
}

export async function renewSubscription(
  id: string,
  durationType: string,
  expiresAt?: string
): Promise<Subscription> {
  const payload: Record<string, string> = { duration_type: durationType };
  if (expiresAt) payload.expires_at = expiresAt;
  const { data } = await api.post(`/subscriptions/${id}/renew`, payload);
  return data;
}

export async function reactivateSubscription(
  id: string,
  durationType = "1_month",
  startsAt?: string,
  expiresAt?: string,
): Promise<Subscription> {
  const payload: Record<string, string> = { duration_type: durationType };
  if (startsAt) payload.starts_at = startsAt;
  if (expiresAt) payload.expires_at = expiresAt;
  const { data } = await api.post(`/subscriptions/${id}/reactivate`, payload);
  return data;
}

// ── Related data for dropdowns ────────────────────────────────
import { listClients, type Client } from "./client-api";
import { listServices, listPlans, type Service, type Plan } from "./catalog-api";

export type { Client, Service, Plan };

export async function getDropdownData(): Promise<{
  clients: Client[];
  services: Service[];
}> {
  const [clients, services] = await Promise.all([listClients(), listServices()]);
  return { clients, services };
}

export async function getPlansForService(
  serviceId: string
): Promise<Plan[]> {
  return listPlans(serviceId);
}
