import type { DemoAuthMetadata } from "@/store/auth";
import { createDemoWorkspaceRepository, type DemoWorkspaceRepository } from "@/features/demo/services/demo-workspace";
import type { TenantPlan } from "@/features/auth/services/auth-api";
import {
  getTenantDashboard,
  type TenantDashboardResponse,
} from "@/features/admin/services/dashboard-api";
import {
  createDemoBaseline,
  readStarterDemoState,
} from "@/features/demo/services/demo-baseline";
import {
  acknowledgeHelpTour,
  getUnseenHelpTour,
  replayHelpTour,
  type HelpTourAcknowledgement,
  type HelpTourRelease,
} from "@/features/help/services/help-api";

export type DataSourceMode = "production" | "demo";
export type DataStorage = "api" | "workspace";
export type DataResource =
  | "dashboard"
  | "settings"
  | "crud"
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
  readonly settings: DataSourceResourceContract<"settings">;
  readonly crud: DataSourceResourceContract<"crud">;
  readonly simulator: DataSourceResourceContract<"simulator">;
  readonly orientation: OrientationDataSourceContract;
}

const productionResources = {
  dashboard: {
    resource: "dashboard",
    storage: "api",
    load: getTenantDashboard,
  },
  settings: { resource: "settings", storage: "api" },
  crud: { resource: "crud", storage: "api" },
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
  crud: { resource: "crud", storage: "workspace" },
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
          const enabledServices = starter.code_services
            .filter((service) => service.enabled)
            .map((service) => service.name);
          return {
            message: "Demo dashboard",
            full_name: starter.profile.business_name,
            email: null,
            tenant_plan: demo.plan,
            mailbox_status: starter.integrations.mailbox.status,
            enabled_code_services: enabledServices,
            access_control_count: starter.blocked_identities.length,
            active_clients: null,
            catalog_services: null,
            active_subscriptions: null,
            subscriptions_expiring_soon: null,
          };
        },
      },
      settings: demoResources.settings,
      crud: demoResources.crud,
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
    context,
    workspace: null,
    dashboard: productionResources.dashboard,
    settings: productionResources.settings,
    crud: productionResources.crud,
    simulator: productionResources.simulator,
    orientation: productionResources.orientation,
  };
}
