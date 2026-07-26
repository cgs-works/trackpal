import { create } from "zustand";
import {
  getAuthFailureCode,
  heartbeatApi,
  loginApi,
  logoutApi,
  refreshApi,
  switchTenantApi,
  type DemoHeartbeatResponse,
  type DemoTenantStatus,
  type TokenResponse,
  type TenantPlan,
  type UserInfo,
} from "@/features/auth/services/auth-api";
import { loadCatalog } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import { useCatalogStore } from "@/store/catalog";
import { clearDemoWorkspace } from "@/features/demo/services/demo-workspace";
import { createDataSource, type DataSourceAdapter } from "@/lib/data-source";

export interface DemoAuthMetadata {
  tenantId: string;
  name: string;
  plan: TenantPlan;
  status: DemoTenantStatus;
  activatedAt: string | null;
  expiresAt: string | null;
  credentialVersion: number;
  serverTime: string;
}

export type AuthOutcome =
  | "anonymous"
  | "authenticated"
  | "logged_out"
  | "authentication_failed"
  | "demo_ended"
  | "demo_credentials_replaced";

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: UserInfo | null;
  activeTenantId: string | null;
  tenantPlan: TenantPlan | null;
  demo: DemoAuthMetadata | null;
  dataSource: DataSourceAdapter;
  authOutcome: AuthOutcome;
  planDowngraded: boolean;
  isMasterSupportContext: boolean;
  isAuthenticated: boolean;
  role: string | null;
  username: string;

  login: (username: string, password: string) => Promise<TokenResponse>;
  refresh: () => Promise<TokenResponse>;
  heartbeat: () => Promise<DemoHeartbeatResponse>;
  logout: () => Promise<void>;
  switchTenant: (tenantId: string | null) => Promise<TokenResponse>;
  setTenantPlan: (plan: TenantPlan | null) => void;
}


function parseTenantPlan(value: string | null): TenantPlan | null {
  return value === "starter" || value === "pro" ? value : null;
}

function loadDemoMetadata(): DemoAuthMetadata | null {
  const raw = localStorage.getItem("demoMetadata");
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    if (
      !("tenantId" in value) || typeof value.tenantId !== "string" ||
      !("name" in value) || typeof value.name !== "string" ||
      !("plan" in value) || (value.plan !== "starter" && value.plan !== "pro") ||
      !("status" in value) ||
      (value.status !== "pending" && value.status !== "active" && value.status !== "expired") ||
      !("activatedAt" in value) ||
      (value.activatedAt !== null && typeof value.activatedAt !== "string") ||
      !("expiresAt" in value) ||
      (value.expiresAt !== null && typeof value.expiresAt !== "string") ||
      !("credentialVersion" in value) || typeof value.credentialVersion !== "number" ||
      !("serverTime" in value) || typeof value.serverTime !== "string"
    ) {
      return null;
    }
    return value as DemoAuthMetadata;
  } catch {
    return null;
  }
}

function metadataFromToken(data: TokenResponse): DemoAuthMetadata | null {
  const tenantId = data.demo_tenant_id ?? data.active_tenant_id;
  if (
    !data.is_demo ||
    !tenantId ||
    !data.demo_name ||
    !data.tenant_plan ||
    !data.demo_status ||
    data.demo_credentials_version === null
  ) {
    return null;
  }
  return {
    tenantId,
    name: data.demo_name,
    plan: data.tenant_plan,
    status: data.demo_status,
    activatedAt: data.demo_activated_at,
    expiresAt: data.demo_expires_at,
    credentialVersion: data.demo_credentials_version,
    serverTime: data.server_time,
  };
}

function metadataFromHeartbeat(
  data: DemoHeartbeatResponse,
  tenantId: string | null,
): DemoAuthMetadata | null {
  const resolvedTenantId = data.demo_tenant_id ?? tenantId;
  if (
    !data.is_demo ||
    !resolvedTenantId ||
    !data.demo_name ||
    !data.tenant_plan ||
    !data.demo_status ||
    data.demo_credentials_version === null
  ) {
    return null;
  }
  return {
    tenantId: resolvedTenantId,
    name: data.demo_name,
    plan: data.tenant_plan,
    status: data.demo_status,
    activatedAt: data.demo_activated_at,
    expiresAt: data.demo_expires_at,
    credentialVersion: data.demo_credentials_version,
    serverTime: data.server_time,
  };
}

function demoEndedError(): Error & {
  response: { data: { detail: "demo_ended" } };
} {
  const error = new Error("demo_ended") as Error & {
    response: { data: { detail: "demo_ended" } };
  };
  error.response = { data: { detail: "demo_ended" } };
  return error;
}
function loadFromStorage() {
  const token = localStorage.getItem("token");
  return {
    token,
    refreshToken: localStorage.getItem("refreshToken"),
    user: JSON.parse(localStorage.getItem("user") || "null") as UserInfo | null,
    activeTenantId: localStorage.getItem("activeTenantId"),
    tenantPlan: parseTenantPlan(localStorage.getItem("tenantPlan")),
    demo: token ? loadDemoMetadata() : null,
  };
}

function saveTokenData(data: TokenResponse) {
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("refreshToken", data.refresh_token);
  localStorage.setItem("user", JSON.stringify(data.user));
  if (data.active_tenant_id) {
    localStorage.setItem("activeTenantId", data.active_tenant_id);
  } else {
    localStorage.removeItem("activeTenantId");
  }
  if (data.tenant_plan) {
    localStorage.setItem("tenantPlan", data.tenant_plan);
  } else {
    localStorage.removeItem("tenantPlan");
  }
  const demo = metadataFromToken(data);
  if (demo) {
    localStorage.setItem("demoMetadata", JSON.stringify(demo));
  } else {
    localStorage.removeItem("demoMetadata");
  }
}

function saveDemoMetadata(demo: DemoAuthMetadata | null) {
  if (demo) {
    localStorage.setItem("demoMetadata", JSON.stringify(demo));
  } else {
    localStorage.removeItem("demoMetadata");
  }
}

function clearTokenData() {
  localStorage.removeItem("token");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("user");
  localStorage.removeItem("activeTenantId");
  localStorage.removeItem("tenantPlan");
  localStorage.removeItem("demoMetadata");
}

function stateFromToken(data: TokenResponse, demo: DemoAuthMetadata | null) {
  const dataSource = createDataSource({
    tenantId: data.active_tenant_id,
    tenantPlan: data.tenant_plan,
    demo,
  });
  return {
    token: data.access_token,
    refreshToken: data.refresh_token,
    user: data.user,
    activeTenantId: data.active_tenant_id,
    tenantPlan: data.tenant_plan,
    demo,
    dataSource,
    authOutcome: "authenticated" as const,
    isMasterSupportContext: data.user.role === "master" && !!data.active_tenant_id,
    isAuthenticated: true,
    role: data.user.role,
    username: data.user.username,
  };
}

function anonymousState(outcome: AuthOutcome) {
  return {
    token: null,
    refreshToken: null,
    user: null,
    activeTenantId: null,
    tenantPlan: null,
    demo: null,
    dataSource: createDataSource({ tenantId: null, tenantPlan: null, demo: null }),
    authOutcome: outcome,
    isMasterSupportContext: false,
    isAuthenticated: false,
    role: null,
    username: "",
  };
}

const initial = loadFromStorage();

export const useAuthStore = create<AuthState>((set, get) => ({
  token: initial.token,
  refreshToken: initial.refreshToken,
  user: initial.user,
  activeTenantId: initial.activeTenantId,
  tenantPlan: initial.tenantPlan,
  demo: initial.demo,
  dataSource: createDataSource({
    tenantId: initial.activeTenantId,
    tenantPlan: initial.tenantPlan,
    demo: initial.demo,
  }),
  authOutcome: initial.token ? "authenticated" : "anonymous",
  planDowngraded: false,
  isMasterSupportContext: initial.user?.role === "master" && !!initial.activeTenantId,
  isAuthenticated: !!initial.token,
  role: initial.user?.role || null,
  username: initial.user?.username || "",

  login: async (username, password) => {
    let data: TokenResponse;
    try {
      data = await loginApi(username, password);
    } catch (error) {
      set({ authOutcome: getAuthFailureCode(error) ?? "authentication_failed" });
      throw error;
    }

    const current = get();
    const planDowngraded =
      current.user?.id === data.user.id &&
      current.activeTenantId === data.active_tenant_id &&
      current.tenantPlan === "pro" &&
      data.tenant_plan === "starter";
    const demo = metadataFromToken(data);
    saveTokenData(data);
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({ ...stateFromToken(data, demo), planDowngraded });
    await loadCatalog();
    return data;
  },

  refresh: async () => {
    const refreshToken = get().refreshToken;
    if (!refreshToken) throw new Error("No refresh token available");
    try {
      const data = await refreshApi(refreshToken);
      const demo = metadataFromToken(data);
      saveTokenData(data);
      set({ ...stateFromToken(data, demo), planDowngraded: false });
      return data;
    } catch (error) {
      const outcome = getAuthFailureCode(error);
      if (outcome) {
        const tenantId = get().demo?.tenantId;
        if (outcome === "demo_ended" && tenantId) clearDemoWorkspace(tenantId);
        clearTokenData();
        set(anonymousState(outcome));
      } else {
        set({ authOutcome: "authentication_failed" });
      }
      throw error;
    }
  },

  heartbeat: async () => {
    try {
      const data = await heartbeatApi();
      const currentDemo = get().demo;
      const tenantId = get().activeTenantId;
      const tenantPlan = data.tenant_plan ?? get().tenantPlan;
      const demo = metadataFromHeartbeat(data, tenantId);

      if (
        currentDemo &&
        (!demo ||
          demo.tenantId !== currentDemo.tenantId ||
          demo.status !== "active")
      ) {
        throw demoEndedError();
      }

      saveDemoMetadata(demo);
      if (data.tenant_plan) {
        localStorage.setItem("tenantPlan", data.tenant_plan);
      }
      set({
        demo,
        tenantPlan,
        authOutcome: "authenticated",
        dataSource: createDataSource(
          { tenantId, tenantPlan, demo },
          get().dataSource.workspace ?? undefined,
        ),
      });
      return data;
    } catch (error) {
      const outcome = getAuthFailureCode(error);
      if (outcome) {
        const tenantId = get().demo?.tenantId;
        if (outcome === "demo_ended" && tenantId) clearDemoWorkspace(tenantId);
        clearTokenData();
        set(anonymousState(outcome));
      } else {
        set({ authOutcome: "authentication_failed" });
      }
      throw error;
    }
  },

  logout: async () => {
    const currentRefresh = localStorage.getItem("refreshToken");
    try {
      await logoutApi(currentRefresh);
    } catch {
      // Logout remains local even when the server is unavailable.
    }
    clearTokenData();
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({ ...anonymousState("logged_out"), planDowngraded: false });
  },

  switchTenant: async (tenantId) => {
    const data = await switchTenantApi(tenantId);
    const demo = metadataFromToken(data);
    saveTokenData(data);
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({ ...stateFromToken(data, demo), planDowngraded: false });
    return data;
  },

  setTenantPlan: (plan) => {
    const current = get();
    const previousPlan = current.tenantPlan;
    if (plan) {
      localStorage.setItem("tenantPlan", plan);
    } else {
      localStorage.removeItem("tenantPlan");
    }
    const dataSource = createDataSource(
      {
        tenantId: current.activeTenantId,
        tenantPlan: plan,
        demo: current.demo,
      },
      current.dataSource.workspace ?? undefined,
    );
    set({
      tenantPlan: plan,
      planDowngraded: previousPlan === "pro" && plan === "starter",
      dataSource,
    });
  },
}));
