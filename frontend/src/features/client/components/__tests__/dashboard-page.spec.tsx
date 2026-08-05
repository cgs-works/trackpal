import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../dashboard-page";
import { useAuthStore } from "@/store/auth";

const fetchClientDashboard = vi.hoisted(() => vi.fn());
const formatPrice = vi.hoisted(() => vi.fn());

vi.mock("../../services/client-dashboard-api", () => ({
  fetchClientDashboard,
}));

vi.mock("@/features/admin/services/catalog-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/admin/services/catalog-api")>();
  return {
    ...actual,
    formatPrice,
  };
});

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`service-icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
  getLocale: () => "en",
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
  formatPrice.mockReset();
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

describe("DashboardPage client i18n", () => {
  const baseDashboard = {
    message: "ok",
    id: "client-1",
    full_name: "Client Demo",
    username: "client_demo",
    phone: null,
    tenant_id: "tenant-1",
    tenant_name: "Provider",
    client_prefix: "demo",
    is_active: true,
  };

  it("localizes subscription table headers", async () => {
    fetchClientDashboard.mockResolvedValue({
      ...baseDashboard,
      subscriptions: [
        {
          id: "sub-1",
          service_name: "Netflix",
          service_icon: null,
          plan_name: "Premium",
          status: "active",
          starts_at: "2026-07-01T00:00:00.000Z",
          expires_at: "2026-08-01T00:00:00.000Z",
        },
      ],
    });

    render(<DashboardPage />);

    for (const key of [
      "frontend.dashboard.client.service",
      "frontend.dashboard.client.plan",
      "frontend.dashboard.client.status",
      "frontend.dashboard.client.start",
      "frontend.dashboard.client.expiry",
    ]) {
      expect(await screen.findAllByText(key)).not.toHaveLength(0);
    }
    // Summary cards + logout + section title all localized
    expect(screen.getByText("frontend.dashboard.client.account")).toBeInTheDocument();
    expect(screen.getByText("frontend.dashboard.client.provider")).toBeInTheDocument();
    expect(screen.getAllByText("frontend.dashboard.client.subscriptions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("frontend.dashboard.tenant.logout")).toBeInTheDocument();
  });

  it("localizes the empty state when there are no subscriptions", async () => {
    fetchClientDashboard.mockResolvedValue({
      ...baseDashboard,
      subscriptions: [],
    });

    render(<DashboardPage />);

    expect(
      await screen.findByText("frontend.dashboard.client.no_subscriptions"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("frontend.dashboard.client.no_subscriptions_hint"),
    ).toBeInTheDocument();
  });

  it("localizes the load error state", async () => {
    fetchClientDashboard.mockRejectedValue(new Error("boom"));

    render(<DashboardPage />);

    expect(
      await screen.findByText("frontend.dashboard.client.load_error"),
    ).toBeInTheDocument();
    expect(screen.getByText("frontend.common.retry")).toBeInTheDocument();
  });
});

describe("DashboardPage client plan price", () => {
  const currency = { code: "VES", symbol: "Bs.", minor_units: 2 };

  it("shows the subscription plan price with the currency symbol", async () => {
    formatPrice.mockReturnValue("Bs. 12,50");

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
      currency,
      subscriptions: [
        {
          id: "sub-1",
          service_name: "Netflix",
          service_icon: "simple-icons:netflix",
          plan_name: "Premium",
          plan_price: "12.50",
          status: "active",
          starts_at: "2026-07-01T00:00:00.000Z",
          expires_at: "2026-08-01T00:00:00.000Z",
        },
      ],
    });

    render(<DashboardPage />);

    // Desktop table and mobile card each show the price — 2 total
    const priceElements = await screen.findAllByText("Bs. 12,50");
    expect(priceElements).toHaveLength(2);
    expect(formatPrice).toHaveBeenCalledWith(
      "12.50",
      currency,
      expect.any(String),
    );
  });

  it("shows Price on request when a plan has no price", async () => {
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
      currency,
      subscriptions: [
        {
          id: "sub-1",
          service_name: "Netflix",
          service_icon: "simple-icons:netflix",
          plan_name: "Premium",
          plan_price: null,
          status: "active",
          starts_at: "2026-07-01T00:00:00.000Z",
          expires_at: "2026-08-01T00:00:00.000Z",
        },
      ],
    });

    render(<DashboardPage />);

    // t() mock returns the key string; both desktop and mobile show it
    const priceOnRequestElements = await screen.findAllByText(
      "frontend.dashboard.client.price_on_request",
    );
    expect(priceOnRequestElements).toHaveLength(2);
    expect(formatPrice).not.toHaveBeenCalled();
  });
});
