import type { DemoAuthMetadata } from "@/store/auth";
import type { TenantPlan } from "@/features/auth/services/auth-api";
import { getBrowserStorage, type BrowserStorageLike } from "@/lib/browser-storage";

export const DEMO_WORKSPACE_SCHEMA_VERSION = 2;
export const DEMO_WORKSPACE_KEY_PREFIX = "trackpal:demo-workspace:";

export type DemoWorkspaceStorageState = "available" | "unavailable" | "quota_exceeded";

export interface DemoWorkspaceRecoveryNotice {
  kind: "reset";
}

export class DemoWorkspaceStorageError extends Error {
  readonly code: "demo_workspace_storage_unavailable" | "demo_workspace_quota_exceeded";

  constructor(code: "demo_workspace_storage_unavailable" | "demo_workspace_quota_exceeded") {
    super(code);
    this.name = "DemoWorkspaceStorageError";
    this.code = code;
  }
}

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
  consumeRecoveryNotice(): DemoWorkspaceRecoveryNotice | null;
  storageState(): DemoWorkspaceStorageState;
  clear(): void;
}

export interface StorageLike extends BrowserStorageLike {
  readonly length?: number;
  key?(index: number): string | null;
}

const unavailableStorage: StorageLike = {
  getItem: () => {
    throw new Error("demo_workspace_storage_unavailable");
  },
  setItem: () => {
    throw new Error("demo_workspace_storage_unavailable");
  },
  removeItem: () => {
    throw new Error("demo_workspace_storage_unavailable");
  },
};

function defaultStorage(): StorageLike {
  return getBrowserStorage() ?? unavailableStorage;
}

function workspaceKey(tenantId: string): string {
  return `${DEMO_WORKSPACE_KEY_PREFIX}${tenantId}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isLifecyclePair(activatedAt: unknown, expiresAt: unknown): boolean {
  if (activatedAt === null && expiresAt === null) return true;
  if (!isTimestamp(activatedAt) || !isTimestamp(expiresAt)) return false;
  return Date.parse(expiresAt) > Date.parse(activatedAt);
}

function hasForbiddenKey(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenKey);
  if (!isRecord(value)) return false;

  for (const [key, child] of Object.entries(value)) {
    const normalized = key.toLowerCase();
    if (
      normalized.includes("password") ||
      normalized.includes("access_token") ||
      normalized.includes("refresh_token") ||
      normalized.includes("session") ||
      normalized.includes("chat") ||
      normalized.includes("credential")
    ) {
      return true;
    }
    if (hasForbiddenKey(child)) return true;
  }
  return false;
}

function isRecordArray(value: unknown, requiredKeys: string[] = []): boolean {
  return Array.isArray(value) && value.every((item) => {
    if (!isRecord(item)) return false;
    return requiredKeys.every((key) => typeof item[key] === "string");
  });
}

function isPlanSpecificState(value: unknown, plan: TenantPlan): value is Record<string, unknown> {
  if (!isRecord(value) || hasForbiddenKey(value)) return false;

  if ("profile" in value) {
    if (!isRecord(value.profile) || typeof value.profile.business_name !== "string") return false;
    if (value.profile.locale !== "en" && value.profile.locale !== "es") return false;
    if (!isRecord(value.integrations)) return false;
    for (const integration of [value.integrations.mailbox, value.integrations.whatsapp]) {
      if (!isRecord(integration) || integration.status !== "connected" || integration.simulated !== true) {
        return false;
      }
    }
    if (!isRecordArray(value.code_services, ["id", "name"])) return false;
    if (!isRecordArray(value.blocked_identities, ["id", "phone"])) return false;
  }

  const proKeys = ["clients", "services", "plans", "subscriptions"];
  const hasProKey = proKeys.some((key) => key in value);
  if (plan === "starter" && hasProKey) return false;
  if (!hasProKey) return true;
  if (!proKeys.every((key) => Array.isArray(value[key]))) return false;
  return (
    isRecordArray(value.clients, ["id", "tenant_id", "full_name"]) &&
    isRecordArray(value.services, ["id", "tenant_id", "name"]) &&
    isRecordArray(value.plans, ["id", "tenant_id", "service_id", "name"]) &&
    isRecordArray(value.subscriptions, ["id", "tenant_id", "client_id", "service_id", "plan_id"])
  );
}

function isWorkspaceEnvelope(value: unknown, tenantId: string): value is DemoWorkspaceEnvelope {
  if (!isRecord(value)) return false;
  if (value.schema_version !== DEMO_WORKSPACE_SCHEMA_VERSION) return false;
  if (value.tenant_id !== tenantId || typeof value.source_name !== "string" || !value.source_name) {
    return false;
  }
  if (value.plan !== "starter" && value.plan !== "pro") return false;
  if (!isLifecyclePair(value.activated_at, value.expires_at)) return false;
  if (
    typeof value.baseline_version !== "number" ||
    !Number.isInteger(value.baseline_version) ||
    value.baseline_version < 1
  ) return false;
  if (!isPlanSpecificState(value.plan_specific, value.plan)) return false;
  if (!isRecord(value.tour_state) || !isTimestamp(value.saved_at)) return false;
  return true;
}

function migrateKnownEnvelope(value: unknown, tenantId: string): DemoWorkspaceEnvelope | null {
  if (!isRecord(value) || value.tenant_id !== tenantId) return null;
  if (value.schema_version === DEMO_WORKSPACE_SCHEMA_VERSION) {
    return isWorkspaceEnvelope(value, tenantId) ? value : null;
  }
  if (value.schema_version !== 1) return null;

  const migrated = {
    ...value,
    schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
    baseline_version:
      typeof value.baseline_version === "number" &&
      Number.isInteger(value.baseline_version) &&
      value.baseline_version >= 1
        ? value.baseline_version
        : 1,
  };
  return isWorkspaceEnvelope(migrated, tenantId) ? migrated : null;
}

function isQuotaError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { name?: unknown; code?: unknown };
  return candidate.name === "QuotaExceededError" || candidate.code === 22 || candidate.code === 1014;
}

function timestampOrNull(value: string | null): string | null {
  return value === null || isTimestamp(value) ? value : null;
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
    activated_at: timestampOrNull(metadata.activatedAt),
    expires_at: timestampOrNull(metadata.expiresAt),
    baseline_version: defaults.baseline_version,
    plan_specific: defaults.plan_specific,
    tour_state: defaults.tour_state,
    saved_at: new Date().toISOString(),
  };
}

export function createDemoWorkspaceRepository(
  tenantId: string,
  storage: StorageLike = defaultStorage(),
): DemoWorkspaceRepository {
  const key = workspaceKey(tenantId);
  let storageState: DemoWorkspaceStorageState = storage === unavailableStorage ? "unavailable" : "available";
  let recoveryNotice: DemoWorkspaceRecoveryNotice | null = null;

  if (storageState === "available") {
    try {
      storage.getItem(key);
    } catch (error) {
      storageState = isQuotaError(error) ? "quota_exceeded" : "unavailable";
    }
  }

  function storageError(error: unknown): DemoWorkspaceStorageError {
    storageState = isQuotaError(error) ? "quota_exceeded" : "unavailable";
    return new DemoWorkspaceStorageError(
      storageState === "quota_exceeded"
        ? "demo_workspace_quota_exceeded"
        : "demo_workspace_storage_unavailable",
    );
  }

  function readRaw(): string | null {
    try {
      return storage.getItem(key);
    } catch (error) {
      throw storageError(error);
    }
  }

  function write(envelope: DemoWorkspaceEnvelope): void {
    try {
      storage.setItem(key, JSON.stringify(envelope));
    } catch (error) {
      throw storageError(error);
    }
  }

  function remove(): void {
    try {
      storage.removeItem(key);
    } catch (error) {
      throw storageError(error);
    }
  }

  function parseEnvelope(raw: string): { envelope: DemoWorkspaceEnvelope | null; migrated: boolean } {
    try {
      const parsed: unknown = JSON.parse(raw);
      const envelope = migrateKnownEnvelope(parsed, tenantId);
      if (!envelope) return { envelope: null, migrated: false };
      return {
        envelope,
        migrated: isRecord(parsed) && parsed.schema_version !== DEMO_WORKSPACE_SCHEMA_VERSION,
      };
    } catch {
      return { envelope: null, migrated: false };
    }
  }

  function readInternal(): DemoWorkspaceEnvelope | null {
    const raw = readRaw();
    if (!raw) return null;
    const parsed = parseEnvelope(raw);
    if (!parsed.envelope) return null;
    if (parsed.migrated) write(parsed.envelope);
    return parsed.envelope;
  }

  function save(metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope {
    const envelope = createEnvelope(metadata, baseline);
    if (!isWorkspaceEnvelope(envelope, tenantId)) {
      throw new Error("invalid_demo_workspace_baseline");
    }
    write(envelope);
    return envelope;
  }

  function isExpiredOrphan(envelope: DemoWorkspaceEnvelope, metadata: DemoAuthMetadata): boolean {
    const reference = Date.parse(metadata.serverTime);
    return Number.isFinite(reference) && !!envelope.expires_at && Date.parse(envelope.expires_at) <= reference;
  }

  function cleanupExpiredOrphans(referenceTimestamp: string): void {
    const reference = Date.parse(referenceTimestamp);
    if (!Number.isFinite(reference) || storage.length === undefined || !storage.key) return;

    try {
      const keys = Array.from({ length: storage.length }, (_, index) => storage.key?.(index));
      for (const candidateKey of keys) {
        if (!candidateKey?.startsWith(DEMO_WORKSPACE_KEY_PREFIX)) continue;
        const raw = storage.getItem(candidateKey);
        if (!raw) continue;
        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch {
          continue;
        }
        if (
          isRecord(parsed) &&
          typeof parsed.expires_at === "string" &&
          isTimestamp(parsed.expires_at) &&
          Date.parse(parsed.expires_at) <= reference
        ) {
          storage.removeItem(candidateKey);
        }
      }
    } catch (error) {
      throw storageError(error);
    }
  }

  const read = (): DemoWorkspaceEnvelope | null => readInternal();

  const ensure = (metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope => {
    if (metadata.tenantId !== tenantId) {
      throw new Error("demo_workspace_identity_mismatch");
    }
    if (metadata.status === "expired") {
      remove();
      throw new Error("demo_workspace_ended");
    }
    cleanupExpiredOrphans(metadata.serverTime);

    const raw = readRaw();
    if (raw) {
      const parsed = parseEnvelope(raw);
      if (parsed.envelope && !isExpiredOrphan(parsed.envelope, metadata)) {
        if (
          parsed.envelope.plan === metadata.plan &&
          parsed.envelope.source_name === metadata.name &&
          parsed.envelope.tenant_id === metadata.tenantId
        ) {
          if (parsed.migrated) write(parsed.envelope);
          return parsed.envelope;
        }
        recoveryNotice ??= { kind: "reset" };
      } else if (parsed.envelope && isExpiredOrphan(parsed.envelope, metadata)) {
        remove();
      } else {
        recoveryNotice ??= { kind: "reset" };
      }
    }
    return save(metadata, baseline);
  };

  const updatePlanSpecific = (
    updater: (planSpecific: Record<string, unknown>) => Record<string, unknown>,
  ): DemoWorkspaceEnvelope | null => {
    const envelope = readInternal();
    if (!envelope) return null;
    const updated: DemoWorkspaceEnvelope = {
      ...envelope,
      plan_specific: updater(envelope.plan_specific),
      saved_at: new Date().toISOString(),
    };
    if (!isRecord(updated.plan_specific) || hasForbiddenKey(updated.plan_specific)) {
      throw new Error("invalid_demo_workspace_state");
    }
    write(updated);
    return updated;
  };

  const saveTourState = (patch: Record<string, unknown>): void => {
    const envelope = readInternal();
    if (!envelope) return;
    write({
      ...envelope,
      tour_state: { ...envelope.tour_state, ...patch },
      saved_at: new Date().toISOString(),
    });
  };

  const reset = (metadata: DemoAuthMetadata, baseline?: PlanBaselineFactory): DemoWorkspaceEnvelope => {
    const existing = readInternal();
    const envelope = createEnvelope(metadata, baseline);
    envelope.tour_state = existing?.tour_state ?? {};
    if (!isWorkspaceEnvelope(envelope, tenantId)) {
      throw new Error("invalid_demo_workspace_baseline");
    }
    write(envelope);
    return envelope;
  };

  return {
    key,
    read,
    ensure,
    saveTourState,
    updatePlanSpecific,
    reset,
    consumeRecoveryNotice: () => {
      const current = recoveryNotice;
      recoveryNotice = null;
      return current;
    },
    storageState: () => storageState,
    clear: remove,
  };
}

export function clearDemoWorkspace(
  tenantId: string,
  storage: StorageLike = defaultStorage(),
): DemoWorkspaceStorageState {
  try {
    storage.removeItem(workspaceKey(tenantId));
    return "available";
  } catch (error) {
    // Lifecycle cleanup is best-effort, but the caller still receives an explicit state.
    return isQuotaError(error) ? "quota_exceeded" : "unavailable";
  }
}
