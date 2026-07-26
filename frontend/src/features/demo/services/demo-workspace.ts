import type { DemoAuthMetadata } from "@/store/auth";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export const DEMO_WORKSPACE_SCHEMA_VERSION = 2;
export const DEMO_WORKSPACE_KEY_PREFIX = "trackpal:demo-workspace:";

export interface DemoWorkspaceEnvelope {
  schema_version: typeof DEMO_WORKSPACE_SCHEMA_VERSION;
  tenant_id: string;
  source_name: string;
  plan: TenantPlan;
  activated_at: string | null;
  expires_at: string | null;
  baseline_version: number;
  plan_specific: Record<string, unknown>;
  tour_state: Record<string, unknown>;
  saved_at: string;
}
export type PlanBaselineFactory = (
  plan: TenantPlan,
  metadata: DemoAuthMetadata,
) => {
  plan_specific: Record<string, unknown>;
  tour_state: Record<string, unknown>;
  baseline_version: number;
};

export interface DemoWorkspaceRepository {
  readonly key: string;
  read(): DemoWorkspaceEnvelope | null;
  ensure(metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope;
  updatePlanSpecific(
    updater: (planSpecific: Record<string, unknown>) => Record<string, unknown>,
  ): DemoWorkspaceEnvelope | null;
  saveTourState(patch: Record<string, unknown>): void;
  reset(metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope;
  clear(): void;
}


interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function workspaceKey(tenantId: string): string {
  return `${DEMO_WORKSPACE_KEY_PREFIX}${tenantId}`;
}

function createEnvelope(
  metadata: DemoAuthMetadata,
  baseline?: PlanBaselineFactory,
): DemoWorkspaceEnvelope {
  const defaults = baseline
    ? baseline(metadata.plan, metadata)
    : { plan_specific: {}, tour_state: {}, baseline_version: 1 };

  return {
    schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
    tenant_id: metadata.tenantId,
    source_name: metadata.name,
    plan: metadata.plan,
    activated_at: metadata.activatedAt,
    expires_at: metadata.expiresAt,
    baseline_version: defaults.baseline_version,
    plan_specific: defaults.plan_specific,
    tour_state: defaults.tour_state,
    saved_at: new Date().toISOString(),
  };
}

function isWorkspaceEnvelope(value: unknown, tenantId: string): value is DemoWorkspaceEnvelope {
  if (!value || typeof value !== "object") return false;
  if (!("schema_version" in value) || value.schema_version !== DEMO_WORKSPACE_SCHEMA_VERSION) {
    return false;
  }
  if (!("tenant_id" in value) || value.tenant_id !== tenantId) return false;
  if (!("plan" in value) || (value.plan !== "starter" && value.plan !== "pro")) {
    return false;
  }
  return (
    "source_name" in value &&
    "activated_at" in value &&
    "expires_at" in value &&
    "baseline_version" in value &&
    "plan_specific" in value &&
    "tour_state" in value &&
    "saved_at" in value
  );
}


export function createDemoWorkspaceRepository(
  tenantId: string,
  storage: StorageLike = localStorage,
): DemoWorkspaceRepository {
  const key = workspaceKey(tenantId);

  const read = (): DemoWorkspaceEnvelope | null => {
    const raw = storage.getItem(key);
    if (!raw) return null;
    try {
      const parsed: unknown = JSON.parse(raw);
      return isWorkspaceEnvelope(parsed, tenantId) ? parsed : null;
    } catch {
      return null;
    }
  };

  const save = (metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope => {
    const envelope = createEnvelope(metadata, baseline);
    storage.setItem(key, JSON.stringify(envelope));
    return envelope;
  };

  const ensure = (metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope => {
    return read() ?? save(metadata, baseline);
  };
  const updatePlanSpecific = (
    updater: (planSpecific: Record<string, unknown>) => Record<string, unknown>,
  ): DemoWorkspaceEnvelope | null => {
    const envelope = read();
    if (!envelope) return null;
    const updated: DemoWorkspaceEnvelope = {
      ...envelope,
      plan_specific: updater(envelope.plan_specific),
      saved_at: new Date().toISOString(),
    };
    storage.setItem(key, JSON.stringify(updated));
    return updated;
  };

  const saveTourState = (patch: Record<string, unknown>): void => {
    const envelope = read();
    if (!envelope) return;
    const updated: DemoWorkspaceEnvelope = {
      ...envelope,
      tour_state: { ...envelope.tour_state, ...patch },
      saved_at: new Date().toISOString(),
    };
    storage.setItem(key, JSON.stringify(updated));
  };

  const reset = (metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope => {
    const existing = read();
    const tour_state = existing?.tour_state ?? {};
    const envelope = createEnvelope(metadata, baseline);
    envelope.tour_state = tour_state;
    storage.setItem(key, JSON.stringify(envelope));
    return envelope;
  };

  return {
    key,
    read,
    ensure,
    saveTourState,
    updatePlanSpecific,
    reset,
    clear: () => storage.removeItem(key),
  };
}

export function clearDemoWorkspace(tenantId: string, storage: StorageLike = localStorage): void {
  storage.removeItem(workspaceKey(tenantId));
}
