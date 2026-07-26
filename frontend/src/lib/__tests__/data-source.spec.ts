import { beforeEach, describe, expect, it } from "vitest";
import {
  createDataSource,
  type DataSourceContext,
} from "../data-source";
import {
  createDemoWorkspaceRepository,
  DEMO_WORKSPACE_SCHEMA_VERSION,
} from "../../features/demo/services/demo-workspace";

const demoContext: DataSourceContext = {
  tenantId: "demo-tenant",
  tenantPlan: "pro",
  demo: {
    tenantId: "demo-tenant",
    name: "Demo Workspace",
    plan: "pro",
    status: "active",
    activatedAt: "2026-07-25T10:00:00.000Z",
    expiresAt: "2026-07-27T10:00:00.000Z",
    credentialVersion: 3,
    serverTime: "2026-07-25T10:00:00.000Z",
  },
};

beforeEach(() => {
  localStorage.clear();
});

describe("authenticated data source selection", () => {
  it("selects the production adapter and keeps the existing API boundary", () => {
    const source = createDataSource({
      tenantId: "tenant-1",
      tenantPlan: "starter",
      demo: null,
    });

    expect(source.mode).toBe("production");
    expect(source.workspace).toBeNull();
    expect(source.dashboard.storage).toBe("api");
    expect(source.settings.storage).toBe("api");
    expect(source.crud.storage).toBe("api");
    expect(source.simulator.storage).toBe("api");
    expect(source.orientation.storage).toBe("api");
  });

  it("selects the demo adapter with a tenant-isolated workspace", () => {
    const source = createDataSource(demoContext);

    expect(source.mode).toBe("demo");
    expect(source.workspace).not.toBeNull();
    expect(source.workspace?.key).toBe("trackpal:demo-workspace:demo-tenant");
    expect(source.dashboard.storage).toBe("workspace");
    expect(source.settings.storage).toBe("workspace");
    expect(source.crud.storage).toBe("workspace");
    expect(source.simulator.storage).toBe("workspace");
    expect(source.orientation.storage).toBe("workspace");
  });
});

describe("demo workspace persistence contract", () => {
  it("persists lifecycle context without credentials or business data", () => {
    const repository = createDemoWorkspaceRepository("demo-tenant");
    const workspace = repository.ensure(demoContext.demo!);

    expect(workspace).toMatchObject({
      schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
      tenant_id: "demo-tenant",
      source_name: "Demo Workspace",
      plan: "pro",
      activated_at: demoContext.demo!.activatedAt,
      expires_at: demoContext.demo!.expiresAt,
    });
    expect(workspace).not.toHaveProperty("password");
    expect(workspace).not.toHaveProperty("access_token");
    expect(workspace).not.toHaveProperty("refresh_token");
    expect(workspace).not.toHaveProperty("clients");
    expect(workspace).not.toHaveProperty("catalog");
    expect(workspace).not.toHaveProperty("subscriptions");
    expect(JSON.stringify(workspace)).not.toMatch(/password|token|client|catalog|subscription/i);
  });
});
