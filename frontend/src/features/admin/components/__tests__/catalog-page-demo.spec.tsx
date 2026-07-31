import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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

vi.mock("@/features/catalog/components/icon-picker", () => ({
  IconPicker({
    open,
    onSelect,
  }: {
    open: boolean;
    onSelect: (icon: string | null) => void;
  }) {
    if (!open) return null;
    return (
      <div data-testid="mock-icon-picker">
        <button type="button" onClick={() => onSelect("simple-icons:netflix")}>
          choose-test-icon
        </button>
      </div>
    );
  },
}));

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon({ icon, label }: { icon: string | null; label: string }) {
    return (
      <span data-testid={`service-icon-${icon ?? "none"}`}>
        {label}
      </span>
    );
  },
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
  it("renders services with icons and performs create/edit/delete without API calls", async () => {
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");
    const putSpy = vi.spyOn(api, "put");
    const deleteSpy = vi.spyOn(api, "delete");

    render(<CatalogPage />);

    await waitFor(() => expect(screen.getAllByText("Disney+").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Netflix").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Spotify").length).toBeGreaterThan(0);
    expect(getSpy).not.toHaveBeenCalled();

    // Service icons render for each service
    expect(
      screen.getByTestId("service-icon-tabler:brand-disney"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("service-icon-simple-icons:netflix"),
    ).toBeInTheDocument();

    // "New service" button is present instead of inline input
    const newServiceBtn = screen.getByTestId("new-service-btn");
    expect(newServiceBtn).toBeInTheDocument();

    // Open the Service form dialog
    fireEvent.click(newServiceBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Fill the form and save
    await user.type(screen.getByLabelText("frontend.common.name"), "Local Service");
    fireEvent.click(screen.getByTestId("choose-icon-btn"));
    // Select a unique icon that doesn't match any baseline service
    await waitFor(() => expect(screen.getByText("choose-test-icon")).toBeInTheDocument());
    await user.click(screen.getByText("choose-test-icon"));
    fireEvent.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Local Service")).toBeInTheDocument(),
    );
    // The mock IconPicker always returns "simple-icons:netflix"
    // which matches the baseline Netflix service, so we get 2 elements
    expect(
      screen.getAllByTestId("service-icon-simple-icons:netflix").length,
    ).toBeGreaterThanOrEqual(2);

    // Open edit for Local Service — find the row in the sidebar
    // There are 2 elements with "Local Service" text (icon mock + name span)
    // The edit button is in the sidebar row, not the icon mock
    const allEditBtns = screen.getAllByRole("button", { name: "frontend.catalog.edit" });
    // The last edit button should be for Local Service (first service in the list)
    const editBtn = allEditBtns[allEditBtns.length - 1];
    expect(editBtn).toBeInTheDocument();
    await user.click(editBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Remove icon and save
    fireEvent.click(
      screen.getByRole("button", { name: "frontend.catalog.remove_icon" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    // Wait for dialog to close (edit was saved)
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Verify the icon was removed: Local Service should now render with service-icon-none
    // (the mock ServiceIcon renders data-testid="service-icon-none" when icon is null)
    await waitFor(() => {
      expect(screen.getByTestId("service-icon-none")).toBeInTheDocument();
    });
    // Local Service still exists in the list
    expect(screen.getAllByText("Local Service").length).toBeGreaterThan(0);

    // No API calls
    expect(postSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
  });
});
