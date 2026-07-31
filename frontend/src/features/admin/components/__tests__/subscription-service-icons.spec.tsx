import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SubscriptionFormDialog } from "../subscription-form-dialog";
import { SubscriptionTable } from "../subscription-table";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`service-icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));

const services = [
  {
    id: "service-1",
    tenant_id: "tenant-1",
    name: "Netflix",
    icon: "simple-icons:netflix",
    created_at: "2026-07-01T00:00:00.000Z",
    updated_at: "2026-07-01T00:00:00.000Z",
  },
  {
    id: "service-2",
    tenant_id: "tenant-1",
    name: "Disney+",
    icon: "tabler:brand-disney",
    created_at: "2026-07-01T00:00:00.000Z",
    updated_at: "2026-07-01T00:00:00.000Z",
  },
  {
    id: "service-3",
    tenant_id: "tenant-1",
    name: "HBO Max",
    icon: "simple-icons:max",
    created_at: "2026-07-01T00:00:00.000Z",
    updated_at: "2026-07-01T00:00:00.000Z",
  },
];

const subscription = {
  id: "sub-1",
  tenant_id: "tenant-1",
  client_id: "client-1",
  service_id: services[0].id,
  plan_id: "plan-1",
  streaming_email: "client@example.test",
  profile_name: null,
  duration_type: "1_month",
  starts_at: "2026-07-01T00:00:00.000Z",
  expires_at: "2026-08-01T00:00:00.000Z",
  cancelled_at: null,
  status: "active",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-01T00:00:00.000Z",
  has_password: false,
  has_pin: false,
};

describe("Subscription service icons", () => {
  it("renders icons in the selected Service and Service options", async () => {
    render(
      <SubscriptionFormDialog
        open
        mode="edit"
        subscription={subscription}
        clients={[]}
        services={services}
        plans={[]}
        loadingPlans={false}
        onServiceChange={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
        saving={false}
        error=""
        onOpenChange={vi.fn()}
      />,
    );

    expect(
      await screen.findByTestId("service-icon-simple-icons:netflix"),
    ).toHaveTextContent("Netflix");
  });

  it("renders ServiceIcon for each option in the service selector dropdown", async () => {
    const user = userEvent.setup();

    render(
      <SubscriptionFormDialog
        open
        mode="create"
        clients={[]}
        services={services}
        plans={[]}
        loadingPlans={false}
        onServiceChange={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
        saving={false}
        error=""
        onOpenChange={vi.fn()}
      />,
    );

    // Open the service selector dropdown
    const serviceTrigger = screen.getByText("frontend.subscriptions.select_service");
    await user.click(serviceTrigger);

    // Each service option should render a ServiceIcon
    const disneyOption = await screen.findByTestId("service-icon-tabler:brand-disney");
    expect(disneyOption).toHaveTextContent("Disney+");

    expect(screen.getByTestId("service-icon-simple-icons:netflix")).toHaveTextContent("Netflix");
    expect(screen.getByTestId("service-icon-simple-icons:max")).toHaveTextContent("HBO Max");
  });

  it("renders icons in Subscription table desktop and mobile views", () => {
    render(
      <SubscriptionTable
        subscriptions={[subscription]}
        clients={{ "client-1": "Client Demo" }}
        services={{ [services[0].id]: services[0] }}
        plans={{ "plan-1": "Premium" }}
        onEdit={vi.fn()}
        onReveal={vi.fn()}
        onCancel={vi.fn()}
        onRenew={vi.fn()}
        onReactivate={vi.fn()}
      />,
    );

    // Desktop table and mobile card each render a ServiceIcon — 2 total
    expect(
      screen.getAllByTestId("service-icon-simple-icons:netflix"),
    ).toHaveLength(2);
    // Service name appears in icon label + text node in both views
    expect(screen.getAllByText("Netflix").length).toBeGreaterThanOrEqual(2);
  });
});
