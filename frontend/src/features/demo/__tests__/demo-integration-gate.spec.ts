import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { loadCatalog } from "@/i18n";
import {
  heartbeatApi,
  loginApi,
  logoutApi,
  refreshApi,
} from "@/features/auth/services/auth-api";
import { changePassword } from "@/features/admin/services/settings-api";
import { createDataSource } from "@/lib/data-source";
import { createDemoBaseline } from "@/features/demo/services/demo-baseline";
import {
  createDemoWorkspaceRepository,
  type DemoWorkspaceRepository,
} from "@/features/demo/services/demo-workspace";
import {
  createSimulatorState,
  transitionSimulator,
} from "@/features/demo/services/simulator-machine";
import {
  createProSimulatorState,
  transitionProSimulator,
} from "@/features/demo/services/pro-simulator-machine";
import type { DemoAuthMetadata } from "@/store/auth";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

vi.mock("@/i18n", () => ({
  loadCatalog: vi.fn().mockResolvedValue(undefined),
  t: (key: string) => key,
}));

const starterMetadata: DemoAuthMetadata = {
  tenantId: "gate-starter",
  name: "Starter Gate Demo",
  plan: "starter",
  status: "active",
  activatedAt: "2026-07-25T12:00:00.000Z",
  expiresAt: "2026-07-27T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-26T12:00:00.000Z",
};

const proMetadata: DemoAuthMetadata = {
  ...starterMetadata,
  tenantId: "gate-pro",
  name: "Pro Gate Demo",
  plan: "pro",
};

const copy = {
  welcome: "welcome",
  servicePrompt: (services: string) => services,
  emptyServices: "empty",
  invalidService: "invalid-service",
  emailPrompt: (service: string) => service,
  invalidEmail: "invalid-email",
  searching: "searching",
  codeFound: (service: string, code: string) => `${service}:${code}`,
  invalidStart: "invalid-start",
  busy: "busy",
  cancelled: "cancelled",
  back: "back",
  invalidNavigation: "invalid-navigation",
};

const proCopy = {
  welcome: "welcome",
  requestMode: "request",
  operationMode: "operation",
  rolePrompt: "role",
  tenantAdminRole: "admin",
  clientRole: "client",
  tenantAdminMenu: (page: number, total: number) => `admin:${page}/${total}`,
  clientMenu: (page: number, total: number) => `client:${page}/${total}`,
  unavailable: "unavailable",
  invalid: "invalid",
  noNextPage: "no-next",
  cancelled: "cancelled",
  cancel: "cancel",
  back: "back",
  next: "next",
};

function repository(metadata: DemoAuthMetadata): DemoWorkspaceRepository {
  const workspace = createDemoWorkspaceRepository(metadata.tenantId);
  workspace.reset(metadata, createDemoBaseline);
  return workspace;
}

function calls(): Array<{ method: string; path: string }> {
  return [
    ...vi.mocked(api.get).mock.calls.map(([path]) => ({ method: "get", path: String(path) })),
    ...vi.mocked(api.post).mock.calls.map(([path]) => ({ method: "post", path: String(path) })),
    ...vi.mocked(api.put).mock.calls.map(([path]) => ({ method: "put", path: String(path) })),
    ...vi.mocked(api.delete).mock.calls.map(([path]) => ({ method: "delete", path: String(path) })),
  ];
}

function assertDemoNetworkAllowlist() {
  const allowed = [
    /^get:\/i18n\/catalog$/,
    /^get:\/help(?:\/.*)?$/,
    /^post:\/auth\/(?:login|refresh|logout|heartbeat)$/,
    /^put:\/me\/password$/,
  ];

  const requests = calls().map(({ method, path }) => `${method}:${path}`);
  expect(requests.every((request) => allowed.some((pattern) => pattern.test(request)))).toBe(true);
}

describe("Demo integration and regression gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it.each([
    ["starter", starterMetadata],
    ["pro", proMetadata],
  ] as const)("keeps the %s narrative in the workspace adapter", async (_plan, metadata) => {
    const workspace = repository(metadata);
    const source = createDataSource(
      { tenantId: metadata.tenantId, tenantPlan: metadata.plan, demo: metadata },
      workspace,
    );

    const dashboard = await source.dashboard.load();
    const profile = await source.settings.loadProfile();
    const updatedProfile = await source.settings.updateProfile({
      full_name: `${metadata.name} Updated`,
    });
    const tenantSettings = await source.settings.updateTenantSettings({ locale: "es" });
    const services = metadata.plan === "pro" ? await source.catalog.listServices() : [];
    const clients = metadata.plan === "pro" ? await source.crud.clients.list() : [];
    const subscriptions = metadata.plan === "pro" ? await source.subscriptions.list() : [];

    expect(source.mode).toBe("demo");
    expect(source.dashboard.storage).toBe("workspace");
    expect(source.settings.storage).toBe("workspace");
    expect(source.catalog.storage).toBe("workspace");
    expect(source.crud.storage).toBe("workspace");
    expect(source.subscriptions.storage).toBe("workspace");
    expect(source.simulator.storage).toBe("workspace");
    expect(profile.full_name).toBe(metadata.name);
    expect(updatedProfile.full_name).toBe(`${metadata.name} Updated`);
    expect(tenantSettings.locale).toBe("es");
    expect(dashboard.tenant_plan).toBe(metadata.plan);
    expect(services).toHaveLength(metadata.plan === "pro" ? 3 : 0);
    expect(clients).toHaveLength(metadata.plan === "pro" ? 5 : 0);
    expect(subscriptions).toHaveLength(metadata.plan === "pro" ? 8 : 0);
    expect(api.get).not.toHaveBeenCalledWith("/dashboard");
    expect(api.get).not.toHaveBeenCalledWith("/tenant-settings");
  });

  it("keeps simulator request and operation narratives local", () => {
    const starter = transitionSimulator(
      createSimulatorState([{ id: "service", name: "Service" }], copy),
      { type: "message", text: "code" },
      copy,
    );
    const pro = transitionProSimulator(
      createProSimulatorState(
        [{ id: "clients", label: "Clients" }],
        [{ id: "profile", label: "Profile" }],
        proCopy,
      ),
      { type: "message", text: "2" },
      proCopy,
    );

    expect(starter.step).toBe("service");
    expect(pro.screen).toBe("role");
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("allows only authentication, password, Help, i18n, and lifecycle traffic", async () => {
    vi.mocked(api.get).mockImplementation(async (path) => ({
      data: String(path).startsWith("/help")
        ? {
            release_id: "demo-tour",
            status: null,
            acknowledged_at: null,
            locale: "en",
            plan: "starter",
            frontend_target_contract_version: "1",
            steps: [],
          }
        : {},
    } as never));

    await loginApi("demo", "password");
    await refreshApi("refresh-token");
    await heartbeatApi();
    await logoutApi("refresh-token");
    await changePassword({ old_password: "password", new_password: "new-password" });
    await loadCatalog();

    const source = createDataSource(
      { tenantId: starterMetadata.tenantId, tenantPlan: "starter", demo: starterMetadata },
      repository(starterMetadata),
    );
    await source.orientation.getUnseen();
    await source.orientation.replay();

    assertDemoNetworkAllowlist();
  });
});
