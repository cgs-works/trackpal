import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../dashboard-page";
import { useAuthStore } from "@/store/auth";

const fetchClientDashboard = vi.hoisted(() => vi.fn());

vi.mock("../../services/client-dashboard-api", () => ({
  fetchClientDashboard,
}));

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`service-icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@tanstack/react-router", () => ({
  Navigate: () => null,
}));

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    isAuthenticated: true,
    role: "client",
  });
  fetchClientDashboard.mockReset();
  vi.restoreAllMocks();
});

describe("DashboardPage client service icons", () => {
  it("shows Service Icons in desktop and mobile Client subscriptions", async () => {
    fetchClientDashboard.mockResolvedValue({
      message: "ok",
      id: "client-1",
      full_name: "Client Demo",
      username: "client_demo",
      phone: null,
      tenant_id: "tenant-1",
      tenant_name: "Provider",
      client_prefix: "demo",
      is_active: true,
      subscriptions: [
        {
          id: "sub-1",
          service_name: "Netflix",
          service_icon: "simple-icons:netflix",
          plan_name: "Premium",
          status: "active",
          starts_at: "2026-07-01T00:00:00.000Z",
          expires_at: "2026-08-01T00:00:00.000Z",
        },
      ],
    });

    render(<DashboardPage />);

    // Desktop table and mobile card each render a ServiceIcon — 2 total
    expect(
      await screen.findAllByTestId("service-icon-simple-icons:netflix"),
    ).toHaveLength(2);
    // Service name appears in icon label + text node in both views
    expect(screen.getAllByText("Netflix").length).toBeGreaterThanOrEqual(2);
  });
});
