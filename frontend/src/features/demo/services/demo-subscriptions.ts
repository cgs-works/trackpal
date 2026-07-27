import type {
  RevealCredentials,
  Subscription,
  SubscriptionCreate,
  SubscriptionFilters,
  SubscriptionUpdate,
} from "@/features/admin/services/subscription-api";
import type { DemoAuthMetadata } from "@/store/auth";
import {
  createDemoBaseline,
  readProDemoState,
  type DemoSubscriptionRelation,
  type ProDemoWorkspaceState,
} from "./demo-baseline";
import type { DemoWorkspaceRepository } from "./demo-workspace";

export type DemoSubscriptionErrorCode =
  | "subscription_not_found"
  | "subscription_validation_failed"
  | "subscription_invalid_relationship"
  | "subscription_invalid_duration"
  | "subscription_pin_requires_profile"
  | "subscription_invalid_dates"
  | "subscription_duplicate"
  | "invalid_demo_workspace";

export class DemoSubscriptionError extends Error {
  readonly code: DemoSubscriptionErrorCode;

  constructor(code: DemoSubscriptionErrorCode, message?: string) {
    super(message ?? code);
    this.name = "DemoSubscriptionError";
    this.code = code;
  }
}

const DURATION_DAYS: Record<string, number> = {
  "1_month": 30,
  "3_months": 90,
  "6_months": 180,
  "9_months": 270,
  "1_year": 365,
};

function now(): string {
  return new Date().toISOString();
}

function parseDate(value: string, code: DemoSubscriptionErrorCode = "subscription_invalid_dates"): Date {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new DemoSubscriptionError(code);
  return date;
}

function isoDate(value: string): string {
  return parseDate(value).toISOString();
}

function calculateExpiration(
  startsAt: string,
  durationType: string,
  customExpiresAt?: string,
): string {
  if (durationType === "custom") {
    if (!customExpiresAt) throw new DemoSubscriptionError("subscription_validation_failed", "custom_duration_requires_expiry");
    return isoDate(customExpiresAt);
  }
  const days = DURATION_DAYS[durationType];
  if (!days) throw new DemoSubscriptionError("subscription_invalid_duration");
  return new Date(parseDate(startsAt).getTime() + days * 86_400_000).toISOString();
}

function validateDateRange(startsAt: string, expiresAt: string): void {
  if (parseDate(expiresAt).getTime() <= parseDate(startsAt).getTime()) {
    throw new DemoSubscriptionError("subscription_invalid_dates");
  }
}

function validateEmail(value: string): string {
  const email = value.trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new DemoSubscriptionError("subscription_validation_failed", "email_invalid");
  }
  return email;
}

function validateDuration(value: string): void {
  if (value !== "custom" && !DURATION_DAYS[value]) {
    throw new DemoSubscriptionError("subscription_invalid_duration");
  }
}

function publicSubscription(relation: DemoSubscriptionRelation): Subscription {
  return {
    id: relation.id,
    tenant_id: relation.tenant_id,
    client_id: relation.client_id,
    service_id: relation.service_id,
    plan_id: relation.plan_id,
    streaming_email: relation.streaming_email,
    profile_name: relation.profile_name,
    duration_type: relation.duration_type,
    starts_at: relation.starts_at,
    expires_at: relation.expires_at,
    cancelled_at: relation.cancelled_at,
    status: relation.status,
    created_at: relation.created_at,
    updated_at: relation.updated_at,
    has_password: Boolean(relation.streaming_secret),
    has_pin: Boolean(relation.pin_secret),
  };
}

function requireState(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
): ProDemoWorkspaceState {
  const envelope = workspace.ensure(metadata, createDemoBaseline);
  const state = readProDemoState(envelope.plan_specific);
  if (!state) throw new DemoSubscriptionError("invalid_demo_workspace");
  return state;
}

function updateState(
  workspace: DemoWorkspaceRepository,
  updater: (state: ProDemoWorkspaceState) => ProDemoWorkspaceState,
): ProDemoWorkspaceState {
  const updated = workspace.updatePlanSpecific((planSpecific) => {
    const state = readProDemoState(planSpecific);
    if (!state) throw new DemoSubscriptionError("invalid_demo_workspace");
    return updater(state) as unknown as Record<string, unknown>;
  });
  if (!updated) throw new DemoSubscriptionError("invalid_demo_workspace");
  const state = readProDemoState(updated.plan_specific);
  if (!state) throw new DemoSubscriptionError("invalid_demo_workspace");
  return state;
}

function validateRelationships(
  state: ProDemoWorkspaceState,
  clientId: string,
  serviceId: string,
  planId: string,
): void {
  if (!state.clients.some((client) => client.id === clientId)) {
    throw new DemoSubscriptionError("subscription_invalid_relationship", "client_not_found");
  }
  if (!state.services.some((service) => service.id === serviceId)) {
    throw new DemoSubscriptionError("subscription_invalid_relationship", "service_not_found");
  }
  const plan = state.plans.find((item) => item.id === planId);
  if (!plan || plan.service_id !== serviceId) {
    throw new DemoSubscriptionError("subscription_invalid_relationship", "plan_not_found");
  }
}

function findSubscription(
  state: ProDemoWorkspaceState,
  id: string,
): DemoSubscriptionRelation {
  const subscription = state.subscriptions.find((item) => item.id === id);
  if (!subscription) throw new DemoSubscriptionError("subscription_not_found");
  return subscription;
}

function validateDuplicate(
  state: ProDemoWorkspaceState,
  clientId: string,
  serviceId: string,
  streamingEmail: string,
  exceptId?: string,
): void {
  const duplicate = state.subscriptions.some((subscription) =>
    subscription.id !== exceptId &&
    subscription.status === "active" &&
    subscription.client_id === clientId &&
    subscription.service_id === serviceId &&
    subscription.streaming_email.toLocaleLowerCase() === streamingEmail.toLocaleLowerCase(),
  );
  if (duplicate) throw new DemoSubscriptionError("subscription_duplicate");
}

function filtered(
  subscriptions: DemoSubscriptionRelation[],
  filters: SubscriptionFilters,
  referenceTime: string,
): Subscription[] {
  const reference = parseDate(referenceTime).getTime();
  const week = reference + 7 * 86_400_000;
  const month = reference + 30 * 86_400_000;
  return subscriptions
    .filter((subscription) => !filters.status || subscription.status === filters.status)
    .filter((subscription) => !filters.client_id || subscription.client_id === filters.client_id)
    .filter((subscription) => !filters.service_id || subscription.service_id === filters.service_id)
    .filter((subscription) => {
      if (!filters.quick_filter) return true;
      const expires = parseDate(subscription.expires_at).getTime();
      if (filters.quick_filter === "expiring") return subscription.status === "active" && expires >= reference && expires <= week;
      if (filters.quick_filter === "expired") return subscription.status === "expired" || expires < reference;
      if (filters.quick_filter === "this_week") return expires >= reference && expires <= week;
      if (filters.quick_filter === "this_month") return expires >= reference && expires <= month;
      return true;
    })
    .map(publicSubscription)
    .sort((a, b) => a.expires_at.localeCompare(b.expires_at));
}

export function createDemoSubscriptions(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
) {
  return {
    async list(filters: SubscriptionFilters = {}): Promise<Subscription[]> {
      return filtered(requireState(workspace, metadata).subscriptions, filters, metadata.serverTime);
    },

    async get(id: string): Promise<Subscription> {
      return publicSubscription(findSubscription(requireState(workspace, metadata), id));
    },

    async create(payload: SubscriptionCreate): Promise<Subscription> {
      const state = requireState(workspace, metadata);
      validateRelationships(state, payload.client_id, payload.service_id, payload.plan_id);
      validateDuration(payload.duration_type);
      const streamingEmail = validateEmail(payload.streaming_email);
      validateDuplicate(state, payload.client_id, payload.service_id, streamingEmail);
      const startsAt = isoDate(payload.starts_at);
      const expiresAt = calculateExpiration(startsAt, payload.duration_type, payload.expires_at);
      validateDateRange(startsAt, expiresAt);
      if (payload.profile_pin && !payload.profile_name?.trim()) {
        throw new DemoSubscriptionError("subscription_pin_requires_profile");
      }
      const timestamp = now();
      const relation: DemoSubscriptionRelation = {
        id: `subscription-${metadata.tenantId}-${Date.now()}`,
        tenant_id: metadata.tenantId,
        client_id: payload.client_id,
        service_id: payload.service_id,
        plan_id: payload.plan_id,
        streaming_email: streamingEmail,
        streaming_secret: payload.streaming_password || null,
        profile_name: payload.profile_name?.trim() || null,
        pin_secret: payload.profile_pin || null,
        duration_type: payload.duration_type,
        starts_at: startsAt,
        expires_at: expiresAt,
        cancelled_at: null,
        status: "active",
        created_at: timestamp,
        updated_at: timestamp,
      };
      updateState(workspace, (current) => ({
        ...current,
        subscriptions: [...current.subscriptions, relation],
      }));
      return publicSubscription(relation);
    },

    async update(id: string, payload: SubscriptionUpdate): Promise<Subscription> {
      const state = requireState(workspace, metadata);
      const existing = findSubscription(state, id);
      const clientId = payload.client_id ?? existing.client_id;
      const serviceId = payload.service_id ?? existing.service_id;
      const planId = payload.plan_id ?? existing.plan_id;
      validateRelationships(state, clientId, serviceId, planId);
      const durationType = payload.duration_type ?? existing.duration_type;
      validateDuration(durationType);
      const startsAt = payload.starts_at ? isoDate(payload.starts_at) : existing.starts_at;
      let expiresAt = existing.expires_at;
      if (payload.expires_at) {
        expiresAt = isoDate(payload.expires_at);
      } else if (payload.duration_type || payload.starts_at) {
        expiresAt = calculateExpiration(startsAt, durationType);
      }
      validateDateRange(startsAt, expiresAt);
      const profileName = payload.profile_name === undefined ? existing.profile_name : payload.profile_name.trim() || null;
      const profilePin = payload.profile_pin === undefined ? existing.pin_secret : payload.profile_pin || null;
      if (profilePin && !profileName) throw new DemoSubscriptionError("subscription_pin_requires_profile");
      const streamingEmail = payload.streaming_email === undefined
        ? existing.streaming_email
        : validateEmail(payload.streaming_email);
      validateDuplicate(state, clientId, serviceId, streamingEmail, id);
      const updated: DemoSubscriptionRelation = {
        ...existing,
        client_id: clientId,
        service_id: serviceId,
        plan_id: planId,
        streaming_email: streamingEmail,
        streaming_secret: payload.streaming_password === undefined ? existing.streaming_secret : payload.streaming_password || null,
        profile_name: profileName,
        pin_secret: profilePin,
        duration_type: durationType,
        starts_at: startsAt,
        expires_at: expiresAt,
        updated_at: now(),
      };
      updateState(workspace, (current) => ({
        ...current,
        subscriptions: current.subscriptions.map((item) => item.id === id ? updated : item),
      }));
      return publicSubscription(updated);
    },

    async reveal(id: string): Promise<RevealCredentials> {
      const relation = findSubscription(requireState(workspace, metadata), id);
      return {
        streaming_password: relation.streaming_secret ?? null,
        profile_pin: relation.pin_secret ?? null,
      };
    },

    async cancel(id: string): Promise<Subscription> {
      const state = requireState(workspace, metadata);
      const existing = findSubscription(state, id);
      const updated = { ...existing, status: "cancelled", cancelled_at: now(), updated_at: now() };
      updateState(workspace, (current) => ({
        ...current,
        subscriptions: current.subscriptions.map((item) => item.id === id ? updated : item),
      }));
      return publicSubscription(updated);
    },

    async renew(id: string, durationType: string, expiresAt?: string): Promise<Subscription> {
      const state = requireState(workspace, metadata);
      const existing = findSubscription(state, id);
      validateDuration(durationType);
      const nextExpiresAt = calculateExpiration(existing.expires_at, durationType, expiresAt);
      validateDateRange(existing.starts_at, nextExpiresAt);
      const updated = {
        ...existing,
        duration_type: durationType,
        expires_at: nextExpiresAt,
        cancelled_at: null,
        status: "active",
        updated_at: now(),
      };
      updateState(workspace, (current) => ({
        ...current,
        subscriptions: current.subscriptions.map((item) => item.id === id ? updated : item),
      }));
      return publicSubscription(updated);
    },

    async reactivate(
      id: string,
      durationType = "1_month",
      startsAt = now(),
      expiresAt?: string,
    ): Promise<Subscription> {
      const state = requireState(workspace, metadata);
      const existing = findSubscription(state, id);
      validateDuration(durationType);
      const nextStartsAt = isoDate(startsAt);
      const nextExpiresAt = calculateExpiration(nextStartsAt, durationType, expiresAt);
      validateDateRange(nextStartsAt, nextExpiresAt);
      const updated = {
        ...existing,
        duration_type: durationType,
        starts_at: nextStartsAt,
        expires_at: nextExpiresAt,
        cancelled_at: null,
        status: "active",
        updated_at: now(),
      };
      updateState(workspace, (current) => ({
        ...current,
        subscriptions: current.subscriptions.map((item) => item.id === id ? updated : item),
      }));
      return publicSubscription(updated);
    },
  };
}

export type DemoSubscriptionsDataSourceContract = ReturnType<typeof createDemoSubscriptions>;
