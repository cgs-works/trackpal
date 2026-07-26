import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/store/auth";
import { useDemoHeartbeat } from "../use-demo-heartbeat";

vi.mock("@/features/auth/services/auth-api", () => ({
  loginApi: vi.fn(),
  logoutApi: vi.fn().mockResolvedValue(undefined),
  refreshApi: vi.fn(),
  heartbeatApi: vi.fn(),
  switchTenantApi: vi.fn(),
  getAuthFailureCode: vi.fn(),
}));

vi.mock("@/i18n", () => ({
  loadCatalog: vi.fn().mockResolvedValue(undefined),
}));

const demoMetadata = {
  tenantId: "demo-tenant-1",
  name: "Test Demo",
  plan: "starter" as const,
  status: "active" as const,
  activatedAt: "2026-07-25T10:00:00Z",
  expiresAt: "2026-07-27T10:00:00Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T10:00:00Z",
};

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  useAuthStore.setState({
    token: "demo-access",
    refreshToken: "demo-refresh",
    user: { id: "u1", role: "tenant", username: "demo-user" },
    activeTenantId: "demo-tenant-1",
    tenantPlan: "starter",
    demo: demoMetadata,
    authOutcome: "authenticated",
    isAuthenticated: true,
    role: "tenant",
    username: "demo-user",
  });
});

describe("useDemoHeartbeat", () => {
  it("returns not paused initially", () => {
    const { result } = renderHook(() => useDemoHeartbeat());
    expect(result.current.isPaused).toBe(false);
    expect(result.current.consecutiveFailures).toBe(0);
  });

  it("returns isPaused false when no demo metadata", () => {
    useAuthStore.setState({ demo: null });
    const { result } = renderHook(() => useDemoHeartbeat());
    expect(result.current.isPaused).toBe(false);
  });
});
