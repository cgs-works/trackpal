import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "../dashboard-page";
import type { Tenant } from "../../services/tenant-api";
import { createTenant, fetchTenants } from "../../services/tenant-api";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({ switchTenant: vi.fn() }),
}));

vi.mock("../../services/tenant-api", () => ({
  fetchTenants: vi.fn(),
  createTenant: vi.fn(),
  updateTenant: vi.fn(),
  activateTenant: vi.fn(),
  deactivateTenant: vi.fn(),
}));
vi.mock("../services/demo-api", () => ({
  fetchDemos: vi.fn().mockResolvedValue([]),
  createDemo: vi.fn(),
  replaceDemoCredentials: vi.fn(),
  deleteDemo: vi.fn(),
}));

const productionTenant: Tenant = {
  id: "production-id",
  full_name: "Production Tenant",
  client_prefix: "prod",
  phone: "12015550001",
  evolution_instance_name: "tenant-production",
  is_active: true,
  username: "production_admin",
  created_at: "2026-07-24T12:00:00Z",
  plan: "pro",
  is_demo: false,
};

const demoTenant: Tenant = {
  ...productionTenant,
  id: "demo-id",
  full_name: "Demo Tenant",
  username: "demo_admin",
  is_demo: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(createTenant).mockResolvedValue({ data: productionTenant });
  vi.mocked(fetchTenants).mockResolvedValue({
    data: [productionTenant, demoTenant],
    meta: { total: 2, active: 2, inactive: 0 },
  });
});

describe("DashboardPage production tab", () => {
  it("sends the selected locale when creating a production tenant", async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getAllByText("Production Tenant").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByRole("button", { name: "Create Business" }));
    await userEvent.type(screen.getByLabelText("Full Name"), "Spanish Business");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Phone"), "+12015550009");
    await userEvent.type(screen.getByLabelText("Username"), "spanish_business");
    await userEvent.type(screen.getByLabelText("Evolution Instance"), "spanish-instance");

    const locale = screen.getByRole("combobox", { name: "Language" });
    await userEvent.click(locale);
    await userEvent.click(screen.getByRole("option", { name: "Spanish" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(createTenant).toHaveBeenCalledWith(
        expect.objectContaining({ locale: "es" }),
      ),
    );
  });

  it("keeps demo tenants out of production rows, counts, search, and actions", async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(screen.getAllByText("Production Tenant").length).toBeGreaterThan(0));
    expect(screen.queryAllByText("Demo Tenant")).toHaveLength(0);
    expect(screen.getByText("Total Businesses").parentElement).toHaveTextContent("1");

    const search = screen.getByPlaceholderText("Search businesses...");
    await userEvent.type(search, "Demo");
    expect(screen.queryAllByText("Demo Tenant")).toHaveLength(0);
    expect(screen.queryAllByText("Production Tenant")).toHaveLength(0);

    await userEvent.clear(search);
    await userEvent.type(search, "Production");
    expect(screen.getAllByText("Production Tenant").length).toBeGreaterThan(0);
  });

  it("exposes separate accessible Production and Demos tabs", async () => {
    render(<DashboardPage />);

    expect(screen.getByRole("tab", { name: "frontend.master.production_tab" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "frontend.master.demos_tab" })).toBeInTheDocument();
    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });
});
