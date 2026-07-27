import type { DemoAuthMetadata } from "@/store/auth";
import {
  createDemoWorkspaceRepository,
  DemoWorkspaceStorageError,
  type DemoWorkspaceRepository,
} from "@/features/demo/services/demo-workspace";
import type { TenantPlan } from "@/features/auth/services/auth-api";
import {
  getTenantDashboard,
  type TenantDashboardResponse,
} from "@/features/admin/services/dashboard-api";
import {
  getTenantSettings,
  updateTenantSettings,
  getProfile,
  updateProfile,
  getMailbox,
  getTimezones,
  getPublicApiKey,
  savePublicApiKeyOrigins,
  regeneratePublicApiKey,
  revokePublicApiKey,
  getTenantCodeServices,
  updateTenantCodeServices,
  type Mailbox,
  type Profile,
  type PublicApiKeyConfig,
  type ProfileUpdate,
  type TenantCodeServiceResponse,
  type TenantSettings,
  type TenantSettingsUpdate,
} from "@/features/admin/services/settings-api";
import {
  getReminderSettings,
  updateReminderSettings,
  type ReminderSettings,
  type ReminderSettingsUpdate,
} from "@/features/admin/services/reminder-api";
import {
  listAccessBlocks,
  createAccessBlock,
  deleteAccessBlock,
  type AccessControlBlock,
} from "@/features/admin/services/access-control-api";
import {
  activateClient,
  createClient,
  deactivateClient,
  deleteClient,
  listClients,
  updateClient,
  type Client,
  type ClientCreate,
  type ClientUpdate,
} from "@/features/admin/services/client-api";
import {
  deletePlan,
  createService,
  deleteService,
  getPlanDeletePreview,
  getServiceDeletePreview,
  listPlans,
  listServices,
  createPlan,
  updatePlan,
  updateService,
  type DeletePreview,
  type Plan,
  type PlanCreate,
  type PlanUpdate,
  type Service,
  type ServiceCreate,
  type ServiceUpdate,
} from "@/features/admin/services/catalog-api";
import { createDemoCatalog } from "@/features/demo/services/demo-catalog";
import {
  createDemoClientCrud,
} from "@/features/demo/services/demo-client-crud";
import { createDemoSubscriptions } from "@/features/demo/services/demo-subscriptions";
import { createDemoSettings } from "@/features/demo/services/demo-settings";
import {
  createDemoBaseline,
  readProDemoState,
  readStarterDemoState,
} from "@/features/demo/services/demo-baseline";
import {
  acknowledgeHelpTour,
  getUnseenHelpTour,
  replayHelpTour,
  type HelpTourAcknowledgement,
  type HelpTourRelease,
} from "@/features/help/services/help-api";
import {
  cancelSubscription,
  createSubscription,
  getSubscription,
  listSubscriptions,
  reactivateSubscription,
  renewSubscription,
  revealCredentials,
  updateSubscription,
  type RevealCredentials,
  type Subscription,
  type SubscriptionCreate,
  type SubscriptionFilters,
  type SubscriptionUpdate,
} from "@/features/admin/services/subscription-api";

const DEMO_EXPIRING_WINDOW_DAYS = 7;
const MILLISECONDS_PER_DAY = 86_400_000;

export type DataSourceMode = "production" | "demo";
export type DataStorage = "api" | "workspace";
export type DataResource =
  | "dashboard"
  | "settings"
  | "catalog"
  | "crud"
  | "subscriptions"
  | "simulator"
  | "orientation";

export interface DataSourceContext {
  tenantId: string | null;
  tenantPlan: TenantPlan | null;
  demo: DemoAuthMetadata | null;
}

export interface DashboardDataSourceContract
  extends DataSourceResourceContract<"dashboard"> {
  load(): Promise<TenantDashboardResponse>;
}

export interface DataSourceResourceContract<Resource extends DataResource> {
  readonly resource: Resource;
  readonly storage: DataStorage;
}
export interface ClientCrudDataSourceContract {
  list(): Promise<Client[]>;
  create(payload: ClientCreate): Promise<Client>;
  update(id: string, payload: ClientUpdate): Promise<Client>;
  deactivate(id: string): Promise<Client>;
  activate(id: string): Promise<Client>;
  getDeletePreview(id: string): Promise<DeletePreview>;
  delete(id: string): Promise<void>;
}

export interface CatalogDataSourceContract
  extends DataSourceResourceContract<"catalog"> {
  listServices(): Promise<Service[]>;
  createService(payload: ServiceCreate): Promise<Service>;
  updateService(id: string, payload: ServiceUpdate): Promise<Service>;
  getServiceDeletePreview(id: string): Promise<DeletePreview>;
  deleteService(id: string): Promise<void>;
  listPlans(serviceId: string): Promise<Plan[]>;
  createPlan(serviceId: string, payload: PlanCreate): Promise<Plan>;
  updatePlan(serviceId: string, planId: string, payload: PlanUpdate): Promise<Plan>;
  getPlanDeletePreview(serviceId: string, planId: string): Promise<DeletePreview>;
  deletePlan(serviceId: string, planId: string): Promise<void>;
}

export interface CrudDataSourceContract
  extends DataSourceResourceContract<"crud"> {
  readonly clients: ClientCrudDataSourceContract;
}

export interface SettingsDataSourceContract
  extends DataSourceResourceContract<"settings"> {
  loadProfile(): Promise<Profile>;
  updateProfile(payload: ProfileUpdate): Promise<Profile>;
  loadReminderSettings(): Promise<ReminderSettings>;
  updateReminderSettings(payload: ReminderSettingsUpdate): Promise<ReminderSettings>;
  loadTenantSettings(): Promise<TenantSettings>;
  updateTenantSettings(payload: TenantSettingsUpdate): Promise<TenantSettings>;
  loadTimezoneOptions(): Promise<{ value: string; label: string; group: string }[]>;
  loadMailbox(): Promise<Mailbox | null>;
  loadPublicApiKey(): Promise<PublicApiKeyConfig | null>;
  savePublicApiKeyOrigins(origins: string[]): Promise<PublicApiKeyConfig>;
  regeneratePublicApiKey(): Promise<PublicApiKeyConfig>;
  revokePublicApiKey(): Promise<void>;
  loadCodeServices(): Promise<TenantCodeServiceResponse>;
  updateCodeServices(serviceKeys: string[]): Promise<TenantCodeServiceResponse>;
  listAccessBlocks(): Promise<AccessControlBlock[]>;
  createAccessBlock(phone: string): Promise<AccessControlBlock>;
  deleteAccessBlock(id: string): Promise<void>;
}
export interface SubscriptionDataSourceContract
  extends DataSourceResourceContract<"subscriptions"> {
  list(filters?: SubscriptionFilters): Promise<Subscription[]>;
  get(id: string): Promise<Subscription>;
  create(payload: SubscriptionCreate): Promise<Subscription>;
  update(id: string, payload: SubscriptionUpdate): Promise<Subscription>;
  reveal(id: string): Promise<RevealCredentials>;
  cancel(id: string): Promise<Subscription>;
  renew(id: string, durationType: string, expiresAt?: string): Promise<Subscription>;
  reactivate(id: string, durationType?: string, startsAt?: string, expiresAt?: string): Promise<Subscription>;
}
export interface OrientationDataSourceContract
  extends DataSourceResourceContract<"orientation"> {
  getUnseen(): Promise<HelpTourRelease>;
  replay(releaseId?: string): Promise<HelpTourRelease>;
  acknowledge(
    releaseId: string,
    status: "completed" | "skipped",
  ): Promise<HelpTourAcknowledgement>;
}

export interface DataSourceAdapter {
  readonly mode: DataSourceMode;
  readonly context: DataSourceContext;
  readonly workspace: DemoWorkspaceRepository | null;
  readonly dashboard: DashboardDataSourceContract;
  readonly settings: SettingsDataSourceContract;
  readonly catalog: CatalogDataSourceContract;
  readonly crud: CrudDataSourceContract;
  readonly subscriptions: SubscriptionDataSourceContract;
  readonly simulator: DataSourceResourceContract<"simulator">;
  readonly orientation: OrientationDataSourceContract;
}

async function getProductionClientDeletePreview(id: string): Promise<DeletePreview> {
  const [clients, subscriptions] = await Promise.all([
    listClients(),
    listSubscriptions({ client_id: id }),
  ]);
  const client = clients.find((item) => item.id === id);
  if (!client) throw new Error("client_not_found");
  const activeSubscriptions = subscriptions.filter((subscription) => subscription.status === "active");
  return {
    target_type: "client",
    target_id: id,
    target_name: client.full_name,
    affected_plan_count: 0,
    active_subscription_count: activeSubscriptions.length,
    historical_subscription_count: subscriptions.length - activeSubscriptions.length,
    total_subscription_count: subscriptions.length,
    active_subscriptions: activeSubscriptions.map((subscription) => ({
      id: subscription.id,
      streaming_email: subscription.streaming_email,
      client_name: client.full_name,
      client_phone: client.phone,
      service_name: "",
      plan_name: "",
      expires_at: subscription.expires_at,
    })),
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

const productionSettings: SettingsDataSourceContract = {
  resource: "settings",
  storage: "api",
  loadProfile: getProfile,
  updateProfile,
  loadReminderSettings: getReminderSettings,
  updateReminderSettings,
  loadTenantSettings: getTenantSettings,
  updateTenantSettings,
  loadTimezoneOptions: getTimezones,
  loadMailbox: getMailbox,
  loadPublicApiKey: getPublicApiKey,
  savePublicApiKeyOrigins: savePublicApiKeyOrigins,
  regeneratePublicApiKey: regeneratePublicApiKey,
  revokePublicApiKey: revokePublicApiKey,
  loadCodeServices: getTenantCodeServices,
  updateCodeServices: updateTenantCodeServices,
  listAccessBlocks,
  createAccessBlock,
  deleteAccessBlock,
};

const productionClientCrud: ClientCrudDataSourceContract = {
  list: listClients,
  create: createClient,
  update: updateClient,
  deactivate: deactivateClient,
  activate: activateClient,
  getDeletePreview: getProductionClientDeletePreview,
  delete: deleteClient,
};

const productionCatalog: CatalogDataSourceContract = {
  resource: "catalog",
  storage: "api",
  listServices,
  createService,
  updateService,
  getServiceDeletePreview,
  deleteService,
  listPlans,
  createPlan,
  updatePlan,
  getPlanDeletePreview,
  deletePlan,
};

const productionSubscriptions: SubscriptionDataSourceContract = {
  resource: "subscriptions",
  storage: "api",
  list: listSubscriptions,
  get: getSubscription,
  create: createSubscription,
  update: updateSubscription,
  reveal: revealCredentials,
  cancel: cancelSubscription,
  renew: renewSubscription,
  reactivate: reactivateSubscription,
};

const productionResources = {
  dashboard: {
    resource: "dashboard",
    storage: "api",
    load: getTenantDashboard,
  },
  settings: productionSettings,
  catalog: productionCatalog,
  crud: { resource: "crud", storage: "api", clients: productionClientCrud },
  subscriptions: productionSubscriptions,
  simulator: { resource: "simulator", storage: "api" },
  orientation: {
    resource: "orientation",
    storage: "api",
    getUnseen: getUnseenHelpTour,
    replay: replayHelpTour,
    acknowledge: acknowledgeHelpTour,
  },
} as const;

const demoResources = {
  settings: { resource: "settings", storage: "workspace" },
  catalog: { resource: "catalog", storage: "workspace" },
  crud: { resource: "crud", storage: "workspace" },
  subscriptions: { resource: "subscriptions", storage: "workspace" },
  simulator: { resource: "simulator", storage: "workspace" },
  orientation: { resource: "orientation", storage: "workspace" },
} as const;

export function createDataSource(
  context: DataSourceContext,
  existingWorkspace?: DemoWorkspaceRepository,
): DataSourceAdapter {
  if (context.demo) {
    const demo = context.demo;
    const workspace =
      existingWorkspace ?? createDemoWorkspaceRepository(demo.tenantId);
    try {
      workspace.ensure(demo, createDemoBaseline);
    } catch (error) {
      if (!(error instanceof DemoWorkspaceStorageError)) throw error;
      // Storage failures are intentionally converted into the repository's explicit
      // unavailable/quota state so the Demo Banner can recover without API fallback.
    }
    return {
      mode: "demo",
      context,
      workspace,
      dashboard: {
        resource: "dashboard",
        storage: "workspace",
        load: async () => {
          const envelope = workspace.ensure(demo, createDemoBaseline);
          const starter = readStarterDemoState(envelope.plan_specific);
          if (!starter) throw new Error("invalid_demo_workspace");
          const pro = demo.plan === "pro" ? readProDemoState(envelope.plan_specific) : null;
          const enabledServices = starter.code_services
            .filter((service) => service.enabled)
            .map((service) => service.name);
          const reference = new Date(demo.serverTime).getTime();
          const expiringEnd = reference + DEMO_EXPIRING_WINDOW_DAYS * MILLISECONDS_PER_DAY;
          const activeSubscriptions = pro?.subscriptions.filter(
            (subscription) => subscription.status === "active",
          ) ?? [];
          const subscriptionsExpiringSoon = activeSubscriptions.filter((subscription) => {
            const expiresAt = new Date(subscription.expires_at).getTime();
            return expiresAt >= reference && expiresAt <= expiringEnd;
          }).length;
          return {
            message: "Demo dashboard",
            full_name: starter.profile.business_name,
            email: null,
            tenant_plan: demo.plan,
            mailbox_status: starter.integrations.mailbox.status,
            enabled_code_services: enabledServices,
            access_control_count: starter.blocked_identities.length,
            active_clients: pro?.clients.filter((client) => client.is_active).length ?? null,
            catalog_services: pro?.services.length ?? null,
            active_subscriptions: pro ? activeSubscriptions.length : null,
            subscriptions_expiring_soon: pro ? subscriptionsExpiringSoon : null,
            reminders_enabled: starter.reminder_settings?.reminders_enabled ?? false,
          };
        },
      },
      settings: {
        ...demoResources.settings,
        ...createDemoSettings(workspace, demo),
      },
      catalog: {
        ...demoResources.catalog,
        ...createDemoCatalog(workspace, demo),
      },
      subscriptions: {
        ...demoResources.subscriptions,
        ...createDemoSubscriptions(workspace, demo),
      },
      crud: {
        ...demoResources.crud,
        clients: createDemoClientCrud(workspace, demo),
      },
      simulator: demoResources.simulator,
      orientation: {
        ...demoResources.orientation,
        getUnseen: async () => {
          const release = await getUnseenHelpTour();
          const status = workspace.read()?.tour_state[release.release_id];
          if (status === "completed" || status === "skipped") {
            throw new Error("help_tour_already_acknowledged");
          }
          return release;
        },
        replay: replayHelpTour,
        acknowledge: async (releaseId, status) => {
          workspace.saveTourState({ [releaseId]: status });
          return {
            release_id: releaseId,
            status,
            acknowledged_at: new Date().toISOString(),
          };
        },
      },
    };
  }

  return {
    mode: "production",
    dashboard: productionResources.dashboard,
    workspace: null,
    context,
    settings: productionResources.settings,
    catalog: productionResources.catalog,
    crud: productionResources.crud,
    subscriptions: productionResources.subscriptions,
    simulator: productionResources.simulator,
    orientation: productionResources.orientation,
  };
}
