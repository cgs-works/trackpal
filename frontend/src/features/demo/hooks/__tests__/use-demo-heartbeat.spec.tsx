import { act, renderHook } from "@testing-library/react";
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

const heartbeatMock = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  heartbeatMock.mockReset();
  heartbeatMock.mockResolvedValue(undefined);
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
    heartbeat: heartbeatMock,
  });
});

describe("useDemoHeartbeat", () => {
  it("runs one cadence without restarting when lifecycle metadata refreshes", async () => {
    const { rerender } = renderHook(() => useDemoHeartbeat());
    await act(async () => {});
    expect(heartbeatMock).toHaveBeenCalledTimes(1);

    useAuthStore.setState({
      demo: { ...demoMetadata, serverTime: "2026-07-25T10:01:00Z" },
    });
    rerender();
    await act(async () => {});

    expect(heartbeatMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(heartbeatMock).toHaveBeenCalledTimes(2);
  });

  it("checks immediately on focus and when a hidden tab becomes visible", async () => {
    renderHook(() => useDemoHeartbeat());
    await act(async () => {});

    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await Promise.resolve();
    });
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(heartbeatMock).toHaveBeenCalledTimes(3);
  });

  it("warns after one failure, pauses after two, and recovers on retry", async () => {
    heartbeatMock
      .mockRejectedValueOnce(new Error("temporary outage"))
      .mockRejectedValueOnce(new Error("temporary outage"));
    const { result } = renderHook(() => useDemoHeartbeat());

    await act(async () => {});
    expect(result.current.consecutiveFailures).toBe(1);
    expect(result.current.isPaused).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(result.current.consecutiveFailures).toBe(2);
    expect(result.current.isPaused).toBe(true);

    heartbeatMock.mockResolvedValueOnce(undefined);
    await act(async () => {
      result.current.retry();
      await Promise.resolve();
    });
    expect(result.current.consecutiveFailures).toBe(0);
    expect(result.current.isPaused).toBe(false);
  });

  it("cleans the cadence and listeners when the demo context unmounts", async () => {
    const { unmount } = renderHook(() => useDemoHeartbeat());
    await act(async () => {});
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(heartbeatMock).toHaveBeenCalledTimes(1);
  });

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
