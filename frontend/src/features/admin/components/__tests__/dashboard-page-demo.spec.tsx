import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../dashboard-page";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import api from "@/lib/api";

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

const metadata = {
  tenantId: "render-dashboard-demo",
  name: "Rendered Dashboard Demo",
  plan: "pro" as const,
  status: "active" as const,
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    dataSource: createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    }),
    demo: metadata,
    tenantPlan: "pro",
    activeTenantId: metadata.tenantId,
    isAuthenticated: true,
    role: "tenant",
    username: "demo_admin",
  });
  vi.restoreAllMocks();
});

describe("DashboardPage rendering", () => {
  it("localizes the mailbox status in the dashboard metric", async () => {
    useAuthStore.setState({
      dataSource: {
        mode: "production",
        dashboard: {
          load: async () => ({
            message: "Dashboard",
            full_name: "Production Tenant",
            tenant_plan: "starter",
            mailbox_status: "connected",
            enabled_code_services: [],
            access_control_count: 0,
            active_clients: null,
            catalog_services: null,
            active_subscriptions: null,
            subscriptions_expiring_soon: null,
          }),
        },
      } as never,
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.mailbox.status_connected")).toBeInTheDocument();
    });
    expect(screen.queryByText("connected")).not.toBeInTheDocument();
  });

  it("renders business labels for enabled platforms", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Disney+")).toBeInTheDocument();
    });
    expect(screen.getByText("HBO Max")).toBeInTheDocument();
    expect(screen.getByText("Prime Video")).toBeInTheDocument();
    expect(screen.getByText("Universal+")).toBeInTheDocument();
    expect(screen.queryByText("hbo_max")).not.toBeInTheDocument();
  });

  it("renders live workspace metrics without calling the dashboard API", async () => {
    const getSpy = vi.spyOn(api, "get");
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.clients.section_title")).toBeInTheDocument();
    });

    const clientsCard = screen.getByText("frontend.clients.section_title").parentElement?.parentElement;
    const subscriptionsCard = screen.getByText("frontend.subscriptions.title").parentElement?.parentElement;
    expect(within(clientsCard!).getByText("3")).toBeInTheDocument();
    expect(within(subscriptionsCard!).getByText("5")).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
  });
});
