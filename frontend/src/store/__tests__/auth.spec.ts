import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../auth";
import { loadCatalog } from "@/i18n";
import {
  heartbeatApi as authHeartbeatApi,
  loginApi,
  refreshApi,
  type TokenResponse,
} from "@/features/auth/services/auth-api";

vi.mock("@/features/auth/services/auth-api", () => ({
  loginApi: vi.fn(),
  logoutApi: vi.fn().mockResolvedValue(undefined),
  refreshApi: vi.fn(),
  heartbeatApi: vi.fn(),
  switchTenantApi: vi.fn(),
  getAuthFailureCode: vi.fn((error: unknown) => {
    if (!error || typeof error !== "object" || !("response" in error)) return null;
    const response = error.response;
    if (!response || typeof response !== "object" || !("data" in response)) return null;
    const data = response.data;
    if (!data || typeof data !== "object" || !("detail" in data)) return null;
    return data.detail === "demo_ended" || data.detail === "demo_credentials_replaced"
      ? data.detail
      : null;
  }),
}));

vi.mock("@/i18n", () => ({
  loadCatalog: vi.fn().mockResolvedValue(undefined),
}));

const demoResponse: TokenResponse = {
  access_token: "demo-access",
  refresh_token: "demo-refresh",
  token_type: "bearer",
  user: { id: "user-demo", role: "tenant", username: "demo-user" },
  active_tenant_id: "demo-tenant",
  demo_tenant_id: "demo-tenant",
  tenant_plan: "pro",
  is_demo: true,
  demo_name: "Demo Workspace",
  demo_status: "active",
  demo_activated_at: "2026-07-25T10:00:00.000Z",
  demo_expires_at: "2026-07-27T10:00:00.000Z",
  demo_credentials_version: 4,
  server_time: "2026-07-25T10:00:00.000Z",
};

const productionResponse: TokenResponse = {
  access_token: "production-access",
  refresh_token: "production-refresh",
  token_type: "bearer",
  user: { id: "user-production", role: "tenant", username: "production-user" },
  active_tenant_id: "tenant-1",
  tenant_plan: "starter",
  is_demo: false,
  demo_tenant_id: null,
  demo_name: null,
  demo_status: null,
  demo_activated_at: null,
  demo_expires_at: null,
  demo_credentials_version: null,
  server_time: "2026-07-25T10:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    token: null,
    refreshToken: null,
    user: null,
    activeTenantId: null,
    tenantPlan: null,
    demo: null,
    authOutcome: "anonymous",
    planDowngraded: false,
    isMasterSupportContext: false,
    isAuthenticated: false,
    role: null,
    username: "",
  });
  vi.clearAllMocks();
});

describe("auth context persistence", () => {
  it("persists immutable demo metadata separately from workspace data", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);

    await useAuthStore.getState().login("demo-user", "password");

    expect(useAuthStore.getState().demo).toEqual({
      tenantId: "demo-tenant",
      name: "Demo Workspace",
      plan: "pro",
      status: "active",
      activatedAt: demoResponse.demo_activated_at,
      expiresAt: demoResponse.demo_expires_at,
      credentialVersion: 4,
      serverTime: demoResponse.server_time,
    });
    expect(JSON.parse(localStorage.getItem("demoMetadata")!)).toMatchObject({
      tenantId: "demo-tenant",
      name: "Demo Workspace",
      plan: "pro",
    });
    expect(localStorage.getItem("trackpal:demo-workspace:demo-tenant")).not.toBeNull();
    expect(vi.mocked(loadCatalog)).toHaveBeenCalledOnce();
  });

  it("restores the browser-local demo locale on the next login", async () => {
    vi.mocked(loginApi).mockResolvedValue(demoResponse);

    await useAuthStore.getState().login("demo-user", "password");
    await useAuthStore.getState().dataSource.settings.updateTenantSettings({ locale: "es" });
    await useAuthStore.getState().logout();
    vi.mocked(loadCatalog).mockClear();

    await useAuthStore.getState().login("demo-user", "password");

    expect(loadCatalog).toHaveBeenCalledWith("es");
  });

  it("uses the production fallback without demo metadata", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(productionResponse);

    await useAuthStore.getState().login("production-user", "password");

    expect(useAuthStore.getState().demo).toBeNull();
    expect(localStorage.getItem("demoMetadata")).toBeNull();
    expect(useAuthStore.getState().authOutcome).toBe("authenticated");
  });
  it("persists metadata returned by a successful refresh", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    const refreshed = {
      ...demoResponse,
      access_token: "demo-access-2",
      refresh_token: "demo-refresh-2",
      demo_credentials_version: 5,
    };
    vi.mocked(refreshApi).mockResolvedValueOnce(refreshed);

    await useAuthStore.getState().refresh();

    expect(useAuthStore.getState().demo?.credentialVersion).toBe(5);
    expect(useAuthStore.getState().token).toBe("demo-access-2");
    expect(JSON.parse(localStorage.getItem("demoMetadata")!).credentialVersion).toBe(5);
  });

  it("updates lifecycle metadata from a successful heartbeat", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    vi.mocked(authHeartbeatApi).mockResolvedValueOnce({
      is_demo: true,
      demo_tenant_id: "demo-tenant",
      demo_name: "Demo Workspace",
      tenant_plan: "pro",
      demo_status: "active",
      demo_activated_at: demoResponse.demo_activated_at,
      demo_expires_at: demoResponse.demo_expires_at,
      demo_credentials_version: 6,
      server_time: "2026-07-25T10:01:00.000Z",
    });

    await useAuthStore.getState().heartbeat();

    expect(useAuthStore.getState().demo?.credentialVersion).toBe(6);
    expect(useAuthStore.getState().demo?.serverTime).toBe("2026-07-25T10:01:00.000Z");
    expect(useAuthStore.getState().dataSource.mode).toBe("demo");
  });
  it("keeps production authentication intact on a non-demo heartbeat", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(productionResponse);
    await useAuthStore.getState().login("production-user", "password");
    vi.mocked(authHeartbeatApi).mockResolvedValueOnce({
      is_demo: false,
      demo_tenant_id: null,
      demo_name: null,
      tenant_plan: "starter",
      demo_status: null,
      demo_activated_at: null,
      demo_expires_at: null,
      demo_credentials_version: null,
      server_time: "2026-07-25T10:01:00.000Z",
    });

    await useAuthStore.getState().heartbeat();

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().authOutcome).toBe("authenticated");
    expect(useAuthStore.getState().demo).toBeNull();
  });
  it("ends a demo session when heartbeat loses its server identity", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    useAuthStore.getState().dataSource.workspace?.ensure(useAuthStore.getState().demo!);
    vi.mocked(authHeartbeatApi).mockResolvedValueOnce({
      is_demo: false,
      demo_tenant_id: null,
      demo_name: null,
      tenant_plan: null,
      demo_status: null,
      demo_activated_at: null,
      demo_expires_at: null,
      demo_credentials_version: null,
      server_time: "2026-07-25T10:01:00.000Z",
    });

    await expect(useAuthStore.getState().heartbeat()).rejects.toThrow("demo_ended");

    expect(useAuthStore.getState().authOutcome).toBe("demo_ended");
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(localStorage.getItem("trackpal:demo-workspace:demo-tenant")).toBeNull();
  });

  it("distinguishes credential replacement while preserving the workspace", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    useAuthStore.getState().dataSource.workspace?.ensure(useAuthStore.getState().demo!);

    vi.mocked(refreshApi).mockRejectedValueOnce({
      response: { data: { detail: "demo_credentials_replaced" } },
    });

    await expect(useAuthStore.getState().refresh()).rejects.toBeDefined();

    expect(useAuthStore.getState().authOutcome).toBe("demo_credentials_replaced");
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(localStorage.getItem("trackpal:demo-workspace:demo-tenant")).not.toBeNull();
  });

  it("clears the matching workspace when the demo lifecycle ends", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    useAuthStore.getState().dataSource.workspace?.ensure(useAuthStore.getState().demo!);

    vi.mocked(authHeartbeatApi).mockRejectedValueOnce({
      response: { data: { detail: "demo_ended" } },
    });

    await expect(useAuthStore.getState().heartbeat()).rejects.toBeDefined();

    expect(useAuthStore.getState().authOutcome).toBe("demo_ended");
    expect(localStorage.getItem("trackpal:demo-workspace:demo-tenant")).toBeNull();
  });

  it("logs out without deleting the browser-local workspace", async () => {
    vi.mocked(loginApi).mockResolvedValueOnce(demoResponse);
    await useAuthStore.getState().login("demo-user", "password");
    useAuthStore.getState().dataSource.workspace?.ensure(useAuthStore.getState().demo!);

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().authOutcome).toBe("logged_out");
    expect(localStorage.getItem("trackpal:demo-workspace:demo-tenant")).not.toBeNull();
  });

});
