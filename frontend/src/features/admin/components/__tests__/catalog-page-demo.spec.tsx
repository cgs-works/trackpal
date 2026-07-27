import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CatalogPage } from "../catalog-page";
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
  tenantId: "render-catalog-demo",
  name: "Rendered Catalog Demo",
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

describe("CatalogPage Demo rendering", () => {
  it("renders the deterministic local catalog and performs CRUD without API calls", async () => {
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");
    const putSpy = vi.spyOn(api, "put");
    const deleteSpy = vi.spyOn(api, "delete");

    render(<CatalogPage />);

    await waitFor(() => expect(screen.getByText("Disney+")).toBeInTheDocument());
    expect(screen.getByText("Netflix")).toBeInTheDocument();
    expect(screen.getByText("Spotify")).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();

    const input = screen.getByPlaceholderText("frontend.catalog.new_service_placeholder");
    await user.type(input, "Local Service");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByText("Local Service")).toBeInTheDocument());

    const row = screen.getByText("Local Service").parentElement;
    expect(row).not.toBeNull();
    const buttons = within(row!).getAllByRole("button");
    await user.click(buttons[1]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByText("frontend.catalog.delete_preview_note")).toHaveLength(2);

    await user.type(screen.getByLabelText("frontend.catalog.confirm_label"), "delete");
    await user.click(screen.getByRole("button", { name: "frontend.catalog.confirm_delete" }));
    await waitFor(() => expect(screen.queryByText("Local Service")).not.toBeInTheDocument());

    expect(postSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });
});
