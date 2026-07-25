import type { DemoAuthMetadata } from "@/store/auth";
import { createDemoWorkspaceRepository, type DemoWorkspaceRepository } from "@/features/demo/services/demo-workspace";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export type DataSourceMode = "production" | "demo";
export type DataStorage = "api" | "workspace";
export type DataResource = "dashboard" | "settings" | "crud" | "simulator";

export interface DataSourceContext {
  tenantId: string | null;
  tenantPlan: TenantPlan | null;
  demo: DemoAuthMetadata | null;
}

export interface DataSourceResourceContract<Resource extends DataResource> {
  readonly resource: Resource;
  readonly storage: DataStorage;
}

export interface DataSourceAdapter {
  readonly mode: DataSourceMode;
  readonly context: DataSourceContext;
  readonly workspace: DemoWorkspaceRepository | null;
  readonly dashboard: DataSourceResourceContract<"dashboard">;
  readonly settings: DataSourceResourceContract<"settings">;
  readonly crud: DataSourceResourceContract<"crud">;
  readonly simulator: DataSourceResourceContract<"simulator">;
}

const productionResources = {
  dashboard: { resource: "dashboard", storage: "api" },
  settings: { resource: "settings", storage: "api" },
  crud: { resource: "crud", storage: "api" },
  simulator: { resource: "simulator", storage: "api" },
} as const;

const demoResources = {
  dashboard: { resource: "dashboard", storage: "workspace" },
  settings: { resource: "settings", storage: "workspace" },
  crud: { resource: "crud", storage: "workspace" },
  simulator: { resource: "simulator", storage: "workspace" },
} as const;

export function createDataSource(
  context: DataSourceContext,
  existingWorkspace?: DemoWorkspaceRepository,
): DataSourceAdapter {
  if (context.demo) {
    return {
      mode: "demo",
      context,
      workspace: existingWorkspace ?? createDemoWorkspaceRepository(context.demo.tenantId),
      dashboard: demoResources.dashboard,
      settings: demoResources.settings,
      crud: demoResources.crud,
      simulator: demoResources.simulator,
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
  };
}
