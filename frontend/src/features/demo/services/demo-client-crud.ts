import type {
  Client,
  ClientCreate,
  ClientUpdate,
} from "@/features/admin/services/client-api";
import {
  createDemoBaseline,
  readProDemoState,
  type ProDemoWorkspaceState,
} from "./demo-baseline";
import type { DemoWorkspaceRepository } from "./demo-workspace";
import type { DemoAuthMetadata } from "@/store/auth";

export type DemoClientErrorCode =
  | "client_local_username_exists"
  | "phone_already_registered"
  | "client_delete_active"
  | "client_has_subscriptions"
  | "client_validation_failed"
  | "client_not_found"
  | "client_update_failed";

export class DemoClientError extends Error {
  readonly code: DemoClientErrorCode;

  constructor(code: DemoClientErrorCode, message?: string) {
    super(message ?? code);
    this.name = "DemoClientError";
    this.code = code;
  }
}

function validateFullName(value: string): string {
  if (!value || value.trim() !== value || !value.trim()) {
    throw new DemoClientError("client_validation_failed", "full_name_required");
  }
  if (!/^[\p{L}\p{N} ]+$/u.test(value)) {
    throw new DemoClientError("client_validation_failed", "full_name_invalid_chars");
  }
  return value.replace(/ {2,}/g, " ");
}

function validateLocalUsername(value: string): string {
  if (!value || value.trim() !== value || !/^[a-z][a-z0-9_]*$/.test(value)) {
    throw new DemoClientError("client_validation_failed", "local_username_invalid");
  }
  if (value.length > 94) {
    throw new DemoClientError("client_validation_failed", "local_username_too_long");
  }
  return value;
}

function normalizePhone(value: string | undefined): string | null {
  if (value === undefined || !value.trim()) return null;
  const raw = value.trim();
  if (raw.includes("@lid") || /[^\d\s+().-]/.test(raw)) {
    throw new DemoClientError("client_validation_failed", "phone_invalid");
  }
  const digits = raw.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15) {
    throw new DemoClientError("client_validation_failed", "phone_invalid");
  }
  return digits;
}

function localUsername(client: Client): string {
  return client.username.startsWith("demo_")
    ? client.username.slice("demo_".length)
    : client.username;
}

function canonicalUsername(local: string): string {
  return `demo_${local}`;
}

function requireState(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
): ProDemoWorkspaceState {
  const envelope = workspace.ensure(metadata, createDemoBaseline);
  const state = readProDemoState(envelope.plan_specific);
  if (!state) throw new DemoClientError("client_update_failed", "invalid_demo_workspace");
  return state;
}

function updateState(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
  updater: (state: ProDemoWorkspaceState) => ProDemoWorkspaceState,
): ProDemoWorkspaceState {
  requireState(workspace, metadata);
  const updated = workspace.updatePlanSpecific((planSpecific) => {
    const state = readProDemoState(planSpecific);
    if (!state) throw new DemoClientError("client_update_failed", "invalid_demo_workspace");
    return updater(state) as unknown as Record<string, unknown>;
  });
  if (!updated) throw new DemoClientError("client_update_failed", "workspace_unavailable");
  const state = readProDemoState(updated.plan_specific);
  if (!state) throw new DemoClientError("client_update_failed", "invalid_demo_workspace");
  return state;
}

function assertUnique(
  clients: Client[],
  local: string,
  phone: string | null,
  exceptId?: string,
): void {
  if (clients.some((client) => client.id !== exceptId && localUsername(client) === local)) {
    throw new DemoClientError("client_local_username_exists");
  }
  if (phone && clients.some((client) => client.id !== exceptId && client.phone === phone)) {
    throw new DemoClientError("phone_already_registered");
  }
}

export function createDemoClientCrud(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
) {
  async function setActive(id: string, isActive: boolean): Promise<Client> {
    const current = requireState(workspace, metadata);
    const existing = current.clients.find((client) => client.id === id);
    if (!existing) throw new DemoClientError("client_not_found");
    const updated = {
      ...existing,
      is_active: isActive,
      updated_at: new Date().toISOString(),
    };
    updateState(workspace, metadata, (state) => ({
      ...state,
      clients: state.clients.map((client) => client.id === id ? updated : client),
    }));
    return updated;
  }
  return {
    async list(): Promise<Client[]> {
      return [...requireState(workspace, metadata).clients];
    },

    async create(payload: ClientCreate): Promise<Client> {
      const fullName = validateFullName(payload.full_name);
      const local = validateLocalUsername(payload.local_username);
      const phone = normalizePhone(payload.phone);
      if (!payload.password || payload.password.length < 6) {
        throw new DemoClientError("client_validation_failed", "password_too_short");
      }
      const current = requireState(workspace, metadata);
      assertUnique(current.clients, local, phone);
      const nextIndex = current.clients.length + 1;
      const now = new Date().toISOString();
      const client: Client = {
        id: `client-${metadata.tenantId}-${nextIndex}-${Date.now()}`,
        tenant_id: metadata.tenantId,
        owner_user_id: `local-owner-${metadata.tenantId}-${nextIndex}`,
        full_name: fullName,
        username: canonicalUsername(local),
        phone,
        is_active: true,
        created_at: now,
        updated_at: now,
      };
      updateState(workspace, metadata, (state) => ({
        ...state,
        clients: [...state.clients, client],
      }));
      return client;
    },

    async update(id: string, payload: ClientUpdate): Promise<Client> {
      const current = requireState(workspace, metadata);
      const existing = current.clients.find((client) => client.id === id);
      if (!existing) throw new DemoClientError("client_not_found");
      const fullName = payload.full_name === undefined
        ? existing.full_name
        : validateFullName(payload.full_name);
      const local = payload.local_username === undefined
        ? localUsername(existing)
        : validateLocalUsername(payload.local_username);
      const phone = payload.phone === undefined
        ? existing.phone
        : normalizePhone(payload.phone);
      assertUnique(current.clients, local, phone, id);
      const updated: Client = {
        ...existing,
        full_name: fullName,
        username: canonicalUsername(local),
        phone,
        updated_at: new Date().toISOString(),
      };
      updateState(workspace, metadata, (state) => ({
        ...state,
        clients: state.clients.map((client) => client.id === id ? updated : client),
      }));
      return updated;
    },

    async deactivate(id: string): Promise<Client> {
      return setActive(id, false);
    },

    async activate(id: string): Promise<Client> {
      return setActive(id, true);
    },

    async delete(id: string): Promise<void> {
      const current = requireState(workspace, metadata);
      const client = current.clients.find((item) => item.id === id);
      if (!client) throw new DemoClientError("client_not_found");
      if (client.is_active) throw new DemoClientError("client_delete_active");
      const subscriptions = (current as ProDemoWorkspaceState & {
        subscriptions?: Array<{ client_id?: string }>;
      }).subscriptions;
      if (subscriptions?.some((subscription) => subscription.client_id === id)) {
        throw new DemoClientError("client_has_subscriptions");
      }
      updateState(workspace, metadata, (state) => ({
        ...state,
        clients: state.clients.filter((item) => item.id !== id),
      }));
    },
  };

}
