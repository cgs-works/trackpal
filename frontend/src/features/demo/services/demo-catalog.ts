import type {
  DeletePreview,
  Plan,
  PlanCreate,
  PlanUpdate,
  Service,
  ServiceCreate,
  ServiceUpdate,
} from "@/features/admin/services/catalog-api";
import type { DemoAuthMetadata } from "@/store/auth";
import {
  createDemoBaseline,
  readProDemoState,
  type DemoSubscriptionRelation,
  type ProDemoWorkspaceState,
} from "./demo-baseline";
import type { DemoWorkspaceRepository } from "./demo-workspace";
import { parseIconReference } from "@/features/catalog/services/icon-reference";

export type DemoCatalogErrorCode =
  | "service_name_already_exists"
  | "plan_name_already_exists"
  | "catalog_name_required"
  | "catalog_name_too_long"
  | "catalog_icon_invalid"
  | "service_not_found"
  | "plan_not_found"
  | "invalid_demo_workspace";

export class DemoCatalogError extends Error {
  readonly code: DemoCatalogErrorCode;

  constructor(code: DemoCatalogErrorCode) {
    super(code);
    this.name = "DemoCatalogError";
    this.code = code;
  }
}

function cleanName(value: string): string {
  const name = value.trim();
  if (!name) throw new DemoCatalogError("catalog_name_required");
  if (name.length > 200) throw new DemoCatalogError("catalog_name_too_long");
  return name;
}

function validateIcon(value: string | null | undefined): string | null {
  if (value === undefined || value === null) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (parseIconReference(trimmed) === null) throw new DemoCatalogError("catalog_icon_invalid");
  return trimmed;
}

function sortByName<T extends { name: string; created_at: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const byName = a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    return byName || a.created_at.localeCompare(b.created_at);
  });
}

function subscriptionRows(
  state: ProDemoWorkspaceState,
  predicate: (subscription: DemoSubscriptionRelation) => boolean,
): DeletePreview["active_subscriptions"] {
  const services = new Map(state.services.map((service) => [service.id, service]));
  const plans = new Map(state.plans.map((plan) => [plan.id, plan]));
  const clients = new Map(state.clients.map((client) => [client.id, client]));
  return state.subscriptions
    .filter(predicate)
    .filter((subscription) => subscription.status === "active")
    .map((subscription) => {
      const service = services.get(subscription.service_id);
      const plan = plans.get(subscription.plan_id);
      const client = clients.get(subscription.client_id);
      return {
        id: subscription.id,
        streaming_email: subscription.streaming_email,
        client_name: client?.full_name ?? null,
        client_phone: client?.phone ?? null,
        service_name: service?.name ?? "",
        plan_name: plan?.name ?? "",
        expires_at: subscription.expires_at,
      };
    });
}

function preview(
  state: ProDemoWorkspaceState,
  targetType: "service" | "plan",
  targetId: string,
  targetName: string,
): DeletePreview {
  const predicate = (subscription: DemoSubscriptionRelation) =>
    targetType === "service"
      ? subscription.service_id === targetId
      : subscription.plan_id === targetId;
  const related = state.subscriptions.filter(predicate);
  const activeSubscriptions = subscriptionRows(state, predicate);
  const affectedPlanCount = targetType === "service"
    ? state.plans.filter((plan) => plan.service_id === targetId).length
    : 0;
  return {
    target_type: targetType,
    target_id: targetId,
    target_name: targetName,
    affected_plan_count: affectedPlanCount,
    active_subscription_count: activeSubscriptions.length,
    historical_subscription_count: related.length - activeSubscriptions.length,
    total_subscription_count: related.length,
    active_subscriptions: activeSubscriptions,
    pagination: {
      page: 1,
      page_size: 10,
      total_items: activeSubscriptions.length,
      total_pages: Math.max(1, Math.ceil(activeSubscriptions.length / 10)),
      has_next: false,
    },
    note: "frontend.catalog.delete_preview_note",
  };
}

function requireState(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
): ProDemoWorkspaceState {
  const envelope = workspace.ensure(metadata, createDemoBaseline);
  const state = readProDemoState(envelope.plan_specific);
  if (!state) throw new DemoCatalogError("invalid_demo_workspace");
  return state;
}

function updateState(
  workspace: DemoWorkspaceRepository,
  updater: (state: ProDemoWorkspaceState) => ProDemoWorkspaceState,
): ProDemoWorkspaceState {
  const updated = workspace.updatePlanSpecific((planSpecific) => {
    const state = readProDemoState(planSpecific);
    if (!state) throw new DemoCatalogError("invalid_demo_workspace");
    return updater(state) as unknown as Record<string, unknown>;
  });
  if (!updated) throw new DemoCatalogError("invalid_demo_workspace");
  const state = readProDemoState(updated.plan_specific);
  if (!state) throw new DemoCatalogError("invalid_demo_workspace");
  return state;
}

export function createDemoCatalog(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
) {
  return {
    async listServices(): Promise<Service[]> {
      return sortByName(requireState(workspace, metadata).services);
    },

    async createService(payload: ServiceCreate): Promise<Service> {
      const name = cleanName(payload.name);
      const icon = validateIcon(payload.icon);
      const current = requireState(workspace, metadata);
      if (current.services.some((service) => service.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
        throw new DemoCatalogError("service_name_already_exists");
      }
      const now = new Date().toISOString();
      const service: Service = {
        id: `service-${metadata.tenantId}-${Date.now()}`,
        tenant_id: metadata.tenantId,
        name,
        icon,
        created_at: now,
        updated_at: now,
      };
      updateState(workspace, (state) => ({
        ...state,
        services: [...state.services, service],
      }));
      return service;
    },

    async updateService(id: string, payload: ServiceUpdate): Promise<Service> {
      const current = requireState(workspace, metadata);
      const existing = current.services.find((service) => service.id === id);
      if (!existing) throw new DemoCatalogError("service_not_found");
      const name = payload.name !== undefined ? cleanName(payload.name) : existing.name;
      if (current.services.some((service) => service.id !== id && service.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
        throw new DemoCatalogError("service_name_already_exists");
      }
      const icon = "icon" in payload ? validateIcon(payload.icon) : existing.icon;
      const updated = { ...existing, name, icon, updated_at: new Date().toISOString() };
      updateState(workspace, (state) => ({
        ...state,
        services: state.services.map((service) => service.id === id ? updated : service),
      }));
      return updated;
    },

    async getServiceDeletePreview(id: string): Promise<DeletePreview> {
      const state = requireState(workspace, metadata);
      const service = state.services.find((item) => item.id === id);
      if (!service) throw new DemoCatalogError("service_not_found");
      return preview(state, "service", id, service.name);
    },

    async deleteService(id: string): Promise<void> {
      const state = requireState(workspace, metadata);
      if (!state.services.some((service) => service.id === id)) {
        throw new DemoCatalogError("service_not_found");
      }
      const planIds = new Set(state.plans.filter((plan) => plan.service_id === id).map((plan) => plan.id));
      updateState(workspace, (current) => ({
        ...current,
        services: current.services.filter((service) => service.id !== id),
        plans: current.plans.filter((plan) => plan.service_id !== id),
        subscriptions: current.subscriptions.filter(
          (subscription) => subscription.service_id !== id && !planIds.has(subscription.plan_id),
        ),
      }));
    },

    async listPlans(serviceId: string): Promise<Plan[]> {
      const state = requireState(workspace, metadata);
      if (!state.services.some((service) => service.id === serviceId)) {
        throw new DemoCatalogError("service_not_found");
      }
      return sortByName(state.plans.filter((plan) => plan.service_id === serviceId));
    },

    async createPlan(serviceId: string, payload: PlanCreate): Promise<Plan> {
      const name = cleanName(payload.name);
      const current = requireState(workspace, metadata);
      if (!current.services.some((service) => service.id === serviceId)) {
        throw new DemoCatalogError("service_not_found");
      }
      if (current.plans.some((plan) => plan.service_id === serviceId && plan.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
        throw new DemoCatalogError("plan_name_already_exists");
      }
      const now = new Date().toISOString();
      const price = payload.price !== undefined ? payload.price : null;
      const plan: Plan = {
        id: `plan-${metadata.tenantId}-${Date.now()}`,
        tenant_id: metadata.tenantId,
        service_id: serviceId,
        name,
        price,
        created_at: now,
        updated_at: now,
      };
      updateState(workspace, (state) => ({ ...state, plans: [...state.plans, plan] }));
      return plan;
    },

    async updatePlan(serviceId: string, planId: string, payload: PlanUpdate): Promise<Plan> {
      const current = requireState(workspace, metadata);
      const existing = current.plans.find((plan) => plan.id === planId && plan.service_id === serviceId);
      if (!existing) throw new DemoCatalogError("plan_not_found");
      const name = cleanName(payload.name);
      if (current.plans.some((plan) => plan.id !== planId && plan.service_id === serviceId && plan.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
        throw new DemoCatalogError("plan_name_already_exists");
      }
      const price = payload.price !== undefined ? payload.price : existing.price;
      const updated = { ...existing, name, price, updated_at: new Date().toISOString() };
      updateState(workspace, (state) => ({
        ...state,
        plans: state.plans.map((plan) => plan.id === planId ? updated : plan),
      }));
      return updated;
    },

    async getPlanDeletePreview(serviceId: string, planId: string): Promise<DeletePreview> {
      const state = requireState(workspace, metadata);
      const plan = state.plans.find((item) => item.id === planId && item.service_id === serviceId);
      if (!plan) throw new DemoCatalogError("plan_not_found");
      return preview(state, "plan", planId, plan.name);
    },

    async deletePlan(serviceId: string, planId: string): Promise<void> {
      const state = requireState(workspace, metadata);
      if (!state.plans.some((plan) => plan.id === planId && plan.service_id === serviceId)) {
        throw new DemoCatalogError("plan_not_found");
      }
      updateState(workspace, (current) => ({
        ...current,
        plans: current.plans.filter((plan) => plan.id !== planId),
        subscriptions: current.subscriptions.filter((subscription) => subscription.plan_id !== planId),
      }));
    },
  };
}

export type DemoCatalogDataSourceContract = ReturnType<typeof createDemoCatalog>;
