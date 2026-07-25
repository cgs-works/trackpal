import type { DemoAuthMetadata } from "@/store/auth";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export const DEMO_WORKSPACE_SCHEMA_VERSION = 1;
export const DEMO_WORKSPACE_KEY_PREFIX = "trackpal:demo-workspace:";

export interface DemoWorkspaceEnvelope {
  schema_version: typeof DEMO_WORKSPACE_SCHEMA_VERSION;
  tenant_id: string;
  source_name: string;
  plan: TenantPlan;
  activated_at: string | null;
  expires_at: string | null;
  baseline_version: number;
  saved_at: string;
}

export interface DemoWorkspaceRepository {
  readonly key: string;
  read(): DemoWorkspaceEnvelope | null;
  ensure(metadata: DemoAuthMetadata): DemoWorkspaceEnvelope;
  reset(metadata: DemoAuthMetadata): DemoWorkspaceEnvelope;
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

function createEnvelope(metadata: DemoAuthMetadata): DemoWorkspaceEnvelope {
  return {
    schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
    tenant_id: metadata.tenantId,
    source_name: metadata.name,
    plan: metadata.plan,
    activated_at: metadata.activatedAt,
    expires_at: metadata.expiresAt,
    baseline_version: 1,
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

  const save = (metadata: DemoAuthMetadata): DemoWorkspaceEnvelope => {
    const envelope = createEnvelope(metadata);
    storage.setItem(key, JSON.stringify(envelope));
    return envelope;
  };

  return {
    key,
    read,
    ensure: (metadata) => read() ?? save(metadata),
    reset: save,
    clear: () => storage.removeItem(key),
  };
}

export function clearDemoWorkspace(tenantId: string, storage: StorageLike = localStorage): void {
  storage.removeItem(workspaceKey(tenantId));
}
