import { render, screen } from "@testing-library/react";
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

const service = {
  id: "service-1",
  tenant_id: "tenant-1",
  name: "Netflix",
  icon: "simple-icons:netflix",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-01T00:00:00.000Z",
};

const subscription = {
  id: "sub-1",
  tenant_id: "tenant-1",
  client_id: "client-1",
  service_id: service.id,
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
        services={[service]}
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

  it("renders icons in Subscription table desktop and mobile views", () => {
    render(
      <SubscriptionTable
        subscriptions={[subscription]}
        clients={{ "client-1": "Client Demo" }}
        services={{ [service.id]: service }}
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
