import { create } from "zustand";
import {
  loginApi,
  logoutApi,
  switchTenantApi,
  type TokenResponse,
  type UserInfo,
} from "@/features/auth/services/auth-api";
import { loadCatalog } from "@/i18n";

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  activeTenantId: string | null
  isAuthenticated: boolean
  role: string | null
  username: string

  login: (username: string, password: string) => Promise<TokenResponse>
  logout: () => Promise<void>
  switchTenant: (tenantId: string | null) => Promise<TokenResponse>
}

function loadFromStorage() {
  return {
    token: localStorage.getItem("token"),
    refreshToken: localStorage.getItem("refreshToken"),
    user: JSON.parse(localStorage.getItem("user") || "null") as UserInfo | null,
    activeTenantId: localStorage.getItem("activeTenantId"),
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
}

function clearTokenData() {
  localStorage.removeItem("token");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("user");
  localStorage.removeItem("activeTenantId");
}

const initial = loadFromStorage();

export const useAuthStore = create<AuthState>((set) => ({
  token: initial.token,
  refreshToken: initial.refreshToken,
  user: initial.user,
  activeTenantId: initial.activeTenantId,
  isAuthenticated: !!initial.token,
  role: initial.user?.role || null,
  username: initial.user?.username || "",

  login: async (username, password) => {
    const data = await loginApi(username, password);
    saveTokenData(data);
    set({
      token: data.access_token,
      refreshToken: data.refresh_token,
      user: data.user,
      activeTenantId: data.active_tenant_id,
      isAuthenticated: true,
      role: data.user.role,
      username: data.user.username,
    });
    // Load i18n catalog after login
    loadCatalog();
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
    set({
      token: null,
      refreshToken: null,
      user: null,
      activeTenantId: null,
      isAuthenticated: false,
      role: null,
      username: "",
    });
  },

  switchTenant: async (tenantId) => {
    const data = await switchTenantApi(tenantId);
    saveTokenData(data);
    set({
      token: data.access_token,
      refreshToken: data.refresh_token,
      user: data.user,
      activeTenantId: data.active_tenant_id,
      isAuthenticated: true,
      role: data.user.role,
      username: data.user.username,
    });
    return data;
  },
}));
