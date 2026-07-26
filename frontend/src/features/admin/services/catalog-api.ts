import api from "@/lib/api";

// ── Service ──────────────────────────────────────────────────
export interface Service {
  id: string;
  tenant_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceCreate {
  name: string;
}

export interface ServiceUpdate {
  name: string;
}

// ── Plan ─────────────────────────────────────────────────────
export interface Plan {
  id: string;
  tenant_id: string;
  service_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface PlanCreate {
  name: string;
}

export interface PlanUpdate {
  name: string;
}

// ── Delete preview ───────────────────────────────────────────
export interface DeleteSubscriptionRow {
  id: string;
  streaming_email: string;
  client_name: string | null;
  client_phone: string | null;
  service_name: string;
  plan_name: string;
  expires_at: string | null;
}

export interface DeletePagination {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
}

export interface DeletePreview {
  target_type: "client" | "service" | "plan";
  target_id: string;
  target_name: string;
  affected_plan_count: number;
  active_subscription_count: number;
  historical_subscription_count: number;
  total_subscription_count: number;
  active_subscriptions: DeleteSubscriptionRow[];
  pagination: DeletePagination;
  note: string;
}

// ── API calls ────────────────────────────────────────────────

// Services
export async function listServices(): Promise<Service[]> {
  const { data } = await api.get("/catalog/services");
  return data;
}

export async function createService(payload: ServiceCreate): Promise<Service> {
  const { data } = await api.post("/catalog/services", payload);
  return data;
}

export async function updateService(
  id: string,
  payload: ServiceUpdate
): Promise<Service> {
  const { data } = await api.put(`/catalog/services/${id}`, payload);
  return data;
}

export async function getServiceDeletePreview(
  serviceId: string,
  page = 1,
  pageSize = 10
): Promise<DeletePreview> {
  const { data } = await api.get(
    `/catalog/services/${serviceId}/delete-preview?page=${page}&page_size=${pageSize}`
  );
  return data;
}

export async function deleteService(
  serviceId: string,
  confirm = true
): Promise<void> {
  await api.delete(`/catalog/services/${serviceId}?confirm=${confirm}`);
}

// Plans
export async function listPlans(serviceId: string): Promise<Plan[]> {
  const { data } = await api.get(`/catalog/services/${serviceId}/plans`);
  return data;
}

export async function createPlan(
  serviceId: string,
  payload: PlanCreate
): Promise<Plan> {
  const { data } = await api.post(
    `/catalog/services/${serviceId}/plans`,
    payload
  );
  return data;
}

export async function updatePlan(
  serviceId: string,
  planId: string,
  payload: PlanUpdate
): Promise<Plan> {
  const { data } = await api.put(
    `/catalog/services/${serviceId}/plans/${planId}`,
    payload
  );
  return data;
}

export async function getPlanDeletePreview(
  serviceId: string,
  planId: string,
  page = 1,
  pageSize = 10
): Promise<DeletePreview> {
  const { data } = await api.get(
    `/catalog/services/${serviceId}/plans/${planId}/delete-preview?page=${page}&page_size=${pageSize}`
  );
  return data;
}

export async function deletePlan(
  serviceId: string,
  planId: string,
  confirm = true
): Promise<void> {
  await api.delete(
    `/catalog/services/${serviceId}/plans/${planId}?confirm=${confirm}`
  );
}
