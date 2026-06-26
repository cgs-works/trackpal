import { create } from "zustand";
import {
  loginApi,
  logoutApi,
  switchTenantApi,
  type TokenResponse,
  type TenantPlan,
  type UserInfo,
} from "@/features/auth/services/auth-api";
import { loadCatalog } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import { useCatalogStore } from "@/store/catalog";

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  activeTenantId: string | null
  tenantPlan: TenantPlan | null
  isMasterSupportContext: boolean
  isAuthenticated: boolean
  role: string | null
  username: string

  login: (username: string, password: string) => Promise<TokenResponse>
  logout: () => Promise<void>
  switchTenant: (tenantId: string | null) => Promise<TokenResponse>
  setTenantPlan: (plan: TenantPlan | null) => void
}

function loadFromStorage() {
  return {
    token: localStorage.getItem("token"),
    refreshToken: localStorage.getItem("refreshToken"),
    user: JSON.parse(localStorage.getItem("user") || "null") as UserInfo | null,
    activeTenantId: localStorage.getItem("activeTenantId"),
    tenantPlan: localStorage.getItem("tenantPlan") as TenantPlan | null,
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
}

function clearTokenData() {
  localStorage.removeItem("token");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("user");
  localStorage.removeItem("activeTenantId");
  localStorage.removeItem("tenantPlan");
}

const initial = loadFromStorage();

export const useAuthStore = create<AuthState>((set) => ({
  token: initial.token,
  refreshToken: initial.refreshToken,
  user: initial.user,
  activeTenantId: initial.activeTenantId,
  tenantPlan: initial.tenantPlan,
  isMasterSupportContext: initial.user?.role === "master" && !!initial.activeTenantId,
  isAuthenticated: !!initial.token,
  role: initial.user?.role || null,
  username: initial.user?.username || "",

  login: async (username, password) => {
    const data = await loginApi(username, password);
    saveTokenData(data);
    // Clear caches on new login
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({
      token: data.access_token,
      refreshToken: data.refresh_token,
      user: data.user,
      activeTenantId: data.active_tenant_id,
      tenantPlan: data.tenant_plan,
      isMasterSupportContext: data.user.role === "master" && !!data.active_tenant_id,
      isAuthenticated: true,
      role: data.user.role,
      username: data.user.username,
    });
    // Load i18n catalog after login (await so catalog is ready before navigate)
    await loadCatalog();
    return data;
  },

  logout: async () => {
    const currentRefresh = localStorage.getItem("refreshToken");
    try {
      await logoutApi(currentRefresh);
    } catch {
      // Ignore errors on logout
    }
    clearTokenData();
    // Clear all caches on logout
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({
      token: null,
      refreshToken: null,
      user: null,
      activeTenantId: null,
      tenantPlan: null,
      isMasterSupportContext: false,
      isAuthenticated: false,
      role: null,
      username: "",
    });
  },

  switchTenant: async (tenantId) => {
    const data = await switchTenantApi(tenantId);
    saveTokenData(data);
    // Clear all caches on tenant switch
    useSettingsStore.getState().clearSettingsCache();
    useCatalogStore.getState().clearAll();
    set({
      token: data.access_token,
      refreshToken: data.refresh_token,
      user: data.user,
      activeTenantId: data.active_tenant_id,
      tenantPlan: data.tenant_plan,
      isMasterSupportContext: data.user.role === "master" && !!data.active_tenant_id,
      isAuthenticated: true,
      role: data.user.role,
      username: data.user.username,
    });
    return data;
  },

  setTenantPlan: (plan) => {
    if (plan) {
      localStorage.setItem("tenantPlan", plan);
    } else {
      localStorage.removeItem("tenantPlan");
    }
    set({ tenantPlan: plan });
  },
}));
