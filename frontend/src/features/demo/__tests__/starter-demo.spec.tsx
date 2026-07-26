import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "@/features/admin/components/dashboard-page";
import { PlanRouteGate } from "@/features/admin/components/plan-route-gate";
import { getAdminNavigationItems } from "@/components/layout/role-navigation";
import {
  createDemoWorkspaceRepository,
  type DemoWorkspaceEnvelope,
} from "@/features/demo/services/demo-workspace";
import { createDemoBaseline } from "@/features/demo/services/demo-baseline";
import type { HelpTourRelease } from "@/features/help/services/help-api";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore, type DemoAuthMetadata } from "@/store/auth";
import api from "@/lib/api";

const i18nState = vi.hoisted(() => ({ locale: "en" as "en" | "es" }));

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));
vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, Record<"en" | "es", string>> = {
      "frontend.dashboard.tenant.title": { en: "Dashboard", es: "Panel" },
      "frontend.dashboard.plan": { en: "Plan", es: "Plan" },
    };
    const value = translations[key]?.[i18nState.locale] ?? key;
    return params ? `${value} ${Object.values(params).join(" ")}` : value;
  },
}));
vi.mock("@tanstack/react-router", () => ({
  Navigate: ({ to }: { to: string }) => <div>navigate:{to}</div>,
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));
vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const metadata: DemoAuthMetadata = {
  tenantId: "starter-demo-1",
  name: "Northwind Demo",
  plan: "starter",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

function seedWorkspace(): DemoWorkspaceEnvelope {
  const repository = createDemoWorkspaceRepository(metadata.tenantId);
  return repository.reset(metadata, createDemoBaseline);
}

function authenticateDemo() {
  const repository = createDemoWorkspaceRepository(metadata.tenantId);
  useAuthStore.setState({
    token: "demo-token",
    refreshToken: "demo-refresh",
    user: { id: "user-1", username: "demo-admin", role: "tenant" },
    activeTenantId: metadata.tenantId,
    tenantPlan: "starter",
    demo: metadata,
    dataSource: createDataSource(
      { tenantId: metadata.tenantId, tenantPlan: "starter", demo: metadata },
      repository,
    ),
    authOutcome: "authenticated",
    planDowngraded: false,
    isMasterSupportContext: false,
    isAuthenticated: true,
    role: "tenant",
    username: "demo-admin",
  });
}

const tour: HelpTourRelease = {
  release_id: "starter-2026-07",
  status: null,
  acknowledged_at: null,
  locale: "en",
  plan: "starter",
  frontend_target_contract_version: "1",
  steps: [],
};

describe("Starter Demo Account integration", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    i18nState.locale = "en";
    seedWorkspace();
    authenticateDemo();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("creates the approved deterministic Starter baseline", () => {
    const first = createDemoBaseline("starter", metadata);
    const second = createDemoBaseline("starter", metadata);

    expect(first).toEqual(second);
    expect(first.plan_specific).toMatchObject({
      profile: { business_name: "Northwind Demo", locale: "en" },
      integrations: {
        mailbox: { status: "connected", simulated: true },
        whatsapp: { status: "connected", simulated: true },
      },
    });
    expect(first.plan_specific.code_services).toHaveLength(3);
    expect(first.plan_specific.blocked_identities).toHaveLength(2);
  });

  it("renders dashboard values from workspace without a dashboard API call", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("Northwind Demo")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith("/dashboard");
  });

  it("keeps Starter navigation and direct Pro routes gated", () => {
    expect(getAdminNavigationItems(false).map((item) => item.to)).toEqual([
      "/admin/dashboard",
      "/admin/settings",
    ]);

    render(
      <PlanRouteGate>
        <div>pro-only-content</div>
      </PlanRouteGate>,
    );

    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.queryByText("pro-only-content")).not.toBeInTheDocument();
  });

  it("reset restores baseline ordering while preserving tour state", () => {
    const repository = useAuthStore.getState().dataSource.workspace!;
    repository.saveTourState({ "starter-2026-07": "skipped" });

    const reset = repository.reset(metadata, createDemoBaseline);

    expect(
      (reset.plan_specific.code_services as Array<{ id: string }>).map(
        (service) => service.id,
      ),
    ).toEqual(["secure-mail", "account-access", "verification-hub"]);
    expect(
      (reset.plan_specific.blocked_identities as Array<{ id: string }>).map(
        (identity) => identity.id,
      ),
    ).toEqual(["blocked-1", "blocked-2"]);
    expect(reset.tour_state).toEqual({ "starter-2026-07": "skipped" });
  });

  it("persists local orientation completion across reload and logout/login", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: tour });
    const orientation = useAuthStore.getState().dataSource.orientation;

    await orientation.acknowledge(tour.release_id, "completed");

    const reloadedRepository = createDemoWorkspaceRepository(metadata.tenantId);
    const persisted = reloadedRepository.read();
    expect(persisted?.tour_state).toEqual({ [tour.release_id]: "completed" });

    useAuthStore.setState({ demo: null });
    authenticateDemo();
    await expect(
      useAuthStore.getState().dataSource.orientation.getUnseen(),
    ).rejects.toThrow("help_tour_already_acknowledged");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("renders the dashboard through the active locale", async () => {
    i18nState.locale = "es";

    render(<DashboardPage />);

    expect(await screen.findByRole("heading", { name: "Panel" })).toBeInTheDocument();
    expect(screen.getByText("Northwind Demo")).toBeInTheDocument();
  });

  it("keeps the production dashboard on its existing API adapter", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        message: "ok",
        full_name: "Production Tenant",
        email: null,
        tenant_plan: "starter",
        mailbox_status: "connected",
        enabled_code_services: [],
        access_control_count: 0,
        active_clients: null,
        catalog_services: null,
        active_subscriptions: null,
        subscriptions_expiring_soon: null,
      },
    });
    const production = createDataSource({
      tenantId: "production-tenant",
      tenantPlan: "starter",
      demo: null,
    });

    await expect(production.dashboard.load()).resolves.toMatchObject({
      full_name: "Production Tenant",
    });
    expect(api.get).toHaveBeenCalledWith("/dashboard");
  });

  it("keeps confirmation controls keyboard operable", async () => {
    const user = userEvent.setup();
    render(
      <button type="button" onClick={() => useAuthStore.getState().dataSource.workspace?.reset(metadata, createDemoBaseline)}>
        Reset Demo Data
      </button>,
    );

    await user.tab();
    expect(screen.getByRole("button", { name: "Reset Demo Data" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(useAuthStore.getState().dataSource.workspace?.read()).not.toBeNull();
  });
});
