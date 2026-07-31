import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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
  id: "service-netflix",
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

describe("Client detail subscription Service column", () => {
  it("renders ServiceIcon next to service name in the subscription table", () => {
    render(
      <SubscriptionTable
        subscriptions={[subscription]}
        clients={{ "client-1": "Avery Stone" }}
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

    // Service name appears alongside the icon
    expect(screen.getAllByText("Netflix").length).toBeGreaterThanOrEqual(2);
  });
});
