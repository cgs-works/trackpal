import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SubscriptionsPage } from "../subscriptions-page";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useCatalogStore } from "@/store/catalog";
import api from "@/lib/api";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const metadata = {
  tenantId: "render-subscriptions-demo",
  name: "Rendered Subscriptions Demo",
  plan: "pro" as const,
  status: "active" as const,
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  useCatalogStore.getState().clearAll();
  useAuthStore.setState({
    dataSource: createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    }),
  });
  vi.restoreAllMocks();
});

describe("SubscriptionsPage Demo rendering", () => {
  it("renders local lifecycle data, filters it, reveals fictitious credentials, and avoids the API", async () => {
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");

    render(<SubscriptionsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("demo.expiring.7@example.test")).toHaveLength(2);
    });
    expect(screen.getAllByText("demo.expired@example.test")).toHaveLength(2);
    expect(getSpy).not.toHaveBeenCalled();

    const search = screen.getByPlaceholderText("frontend.subscriptions.search");
    await user.type(search, "expiring.7");
    await waitFor(() => {
      expect(screen.getAllByText("demo.expiring.7@example.test")).toHaveLength(2);
      expect(screen.queryAllByText("demo.expired@example.test")).toHaveLength(0);
    });

    await user.click(screen.getAllByTitle("frontend.subscriptions.reveal")[0]);
    await waitFor(() => expect(screen.getByText("demo-expiring-7-secret")).toBeInTheDocument());
    expect(postSpy).not.toHaveBeenCalled();
  });
});
