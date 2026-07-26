import type { AccessControlBlock } from "@/features/admin/services/access-control-api";
import type {
  Mailbox,
  Profile,
  ProfileUpdate,
  TenantCodeService,
  TenantSettings,
  TenantSettingsUpdate,
} from "@/features/admin/services/settings-api";
import type { ReminderSettings, ReminderSettingsUpdate } from "@/features/admin/services/reminder-api";
import type { DemoAuthMetadata } from "@/store/auth";
import { createDemoBaseline, readStarterDemoState, type StarterDemoWorkspaceState } from "./demo-baseline";
import type { DemoWorkspaceRepository } from "./demo-workspace";

function now(metadata: DemoAuthMetadata): string {
  return metadata.serverTime;
}

function requireState(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
): StarterDemoWorkspaceState {
  const envelope = workspace.ensure(metadata, createDemoBaseline);
  const state = readStarterDemoState(envelope.plan_specific);
  if (!state) throw new Error("invalid_demo_workspace");
  return state;
}

function updateState(
  workspace: DemoWorkspaceRepository,
  updater: (state: StarterDemoWorkspaceState) => StarterDemoWorkspaceState,
): StarterDemoWorkspaceState {
  const updated = workspace.updatePlanSpecific((planSpecific) => {
    const state = readStarterDemoState(planSpecific);
    if (!state) throw new Error("invalid_demo_workspace");
    return updater(state) as unknown as Record<string, unknown>;
  });
  if (!updated) throw new Error("invalid_demo_workspace");
  const state = readStarterDemoState(updated.plan_specific);
  if (!state) throw new Error("invalid_demo_workspace");
  return state;
}

function defaultReminderSettings(metadata: DemoAuthMetadata): ReminderSettings {
  const timestamp = now(metadata);
  return {
    id: `reminders-${metadata.tenantId}`,
    tenant_id: metadata.tenantId,
    warning_days: [7, 3, 1],
    reminder_time: "09:00",
    recipient_mode: "tenant_only",
    reminders_enabled: false,
    custom_message_tenant: null,
    custom_message_client: null,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function defaultTenantSettings(metadata: DemoAuthMetadata): TenantSettings {
  const timestamp = now(metadata);
  return {
    tenant_id: metadata.tenantId,
    locale: "en",
    timezone: "UTC",
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function demoProfile(
  metadata: DemoAuthMetadata,
  state: StarterDemoWorkspaceState,
): Profile {
  const timestamp = now(metadata);
  return {
    role: "tenant",
    username: `demo_${metadata.tenantId}`,
    name: state.profile.business_name,
    full_name: state.profile.business_name,
    tenant_id: metadata.tenantId,
    tenant_name: state.profile.business_name,
    client_prefix: null,
    locale: state.profile.locale,
    timezone: state.tenant_settings?.timezone ?? "UTC",
    email: state.profile.email ?? null,
    phone: state.profile.phone ?? null,
    is_active: true,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function fixedMailbox(metadata: DemoAuthMetadata): Mailbox {
  const timestamp = now(metadata);
  return {
    id: `mailbox-${metadata.tenantId}`,
    tenant_id: metadata.tenantId,
    mailbox_email: "demo.mailbox@example.test",
    provider: "imap_custom",
    auth_method: "demo",
    status: "connected",
    oauth_provider_user_id: null,
    oauth_provider_email: null,
    imap_host: "demo-mailbox.local",
    imap_port: 993,
    imap_ssl: true,
    last_connection_test_at: timestamp,
    last_connection_error: null,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

export function createDemoSettings(
  workspace: DemoWorkspaceRepository,
  metadata: DemoAuthMetadata,
) {
  return {
    async loadProfile(): Promise<Profile> {
      return demoProfile(metadata, requireState(workspace, metadata));
    },

    async updateProfile(payload: ProfileUpdate): Promise<Profile> {
      const state = updateState(workspace, (existing) => ({
        ...existing,
        profile: {
          ...existing.profile,
          business_name: payload.full_name?.trim() || existing.profile.business_name,
          email: payload.email?.trim() || existing.profile.email || null,
          phone: payload.phone?.trim() || existing.profile.phone || null,
        },
      }));
      return demoProfile(metadata, state);
    },

    async loadReminderSettings(): Promise<ReminderSettings> {
      const state = requireState(workspace, metadata);
      return state.reminder_settings ?? defaultReminderSettings(metadata);
    },

    async updateReminderSettings(payload: ReminderSettingsUpdate): Promise<ReminderSettings> {
      const current = await this.loadReminderSettings();
      const settings = { ...current, ...payload, updated_at: now(metadata) };
      const state = updateState(workspace, (existing) => ({
        ...existing,
        reminder_settings: settings,
      }));
      return state.reminder_settings ?? settings;
    },

    async loadTenantSettings(): Promise<TenantSettings> {
      const state = requireState(workspace, metadata);
      return state.tenant_settings ?? defaultTenantSettings(metadata);
    },

    async updateTenantSettings(payload: TenantSettingsUpdate): Promise<TenantSettings> {
      const current = await this.loadTenantSettings();
      const settings = { ...current, ...payload, updated_at: now(metadata) };
      const state = updateState(workspace, (existing) => ({
        ...existing,
        profile: {
          ...existing.profile,
          locale: settings.locale as "en" | "es",
        },
        tenant_settings: settings,
      }));
      return state.tenant_settings ?? settings;
    },

    async loadTimezoneOptions(): Promise<{ value: string; label: string; group: string }[]> {
      return [{ value: "UTC", label: "UTC", group: "UTC" }];
    },

    async loadMailbox(): Promise<Mailbox> {
      return fixedMailbox(metadata);
    },

    async loadCodeServices(): Promise<{ tenant_id: string; services: TenantCodeService[] }> {
      return {
        tenant_id: metadata.tenantId,
        services: requireState(workspace, metadata).code_services.map((service) => ({
          service_key: service.id,
          label: service.name,
          is_selected: service.enabled,
          is_globally_active: true,
        })),
      };
    },

    async updateCodeServices(serviceKeys: string[]): Promise<{ tenant_id: string; services: TenantCodeService[] }> {
      const selected = new Set(serviceKeys);
      const state = updateState(workspace, (existing) => ({
        ...existing,
        code_services: existing.code_services.map((service) => ({
          ...service,
          enabled: selected.has(service.id),
        })),
      }));
      return {
        tenant_id: metadata.tenantId,
        services: state.code_services.map((service) => ({
          service_key: service.id,
          label: service.name,
          is_selected: service.enabled,
          is_globally_active: true,
        })),
      };
    },

    async listAccessBlocks(): Promise<AccessControlBlock[]> {
      const state = requireState(workspace, metadata);
      return state.blocked_identities.map((block) => ({
        id: block.id,
        tenant_id: metadata.tenantId,
        phone: block.phone,
        whatsapp_lid: null,
        created_at: now(metadata),
        updated_at: now(metadata),
      }));
    },

    async createAccessBlock(phone: string): Promise<AccessControlBlock> {
      const normalized = phone.trim();
      if (!normalized) throw new Error("phone_required");
      const block = {
        id: `blocked-${metadata.tenantId}-${Date.now()}`,
        phone: normalized,
      };
      updateState(workspace, (existing) => ({
        ...existing,
        blocked_identities: [...existing.blocked_identities, block],
      }));
      return {
        id: block.id,
        tenant_id: metadata.tenantId,
        phone: block.phone,
        whatsapp_lid: null,
        created_at: now(metadata),
        updated_at: now(metadata),
      };
    },

    async deleteAccessBlock(id: string): Promise<void> {
      updateState(workspace, (existing) => ({
        ...existing,
        blocked_identities: existing.blocked_identities.filter((block) => block.id !== id),
      }));
    },
  };
}
