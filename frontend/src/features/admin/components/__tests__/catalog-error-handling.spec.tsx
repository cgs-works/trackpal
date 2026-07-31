/**
 * Tests for catalog error message handling (Finding 1 fix).
 *
 * Verifies that catalogErrorMessage properly maps error codes from:
 * - error.code
 * - error.message
 * - Axios response.data.detail
 *
 * to i18n keys via CATALOG_ERROR_KEYS.
 */
import { render, screen, waitFor } from "@testing-library/react";
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
  IconPicker({ open }: { open: boolean; onSelect: (icon: string | null) => void }) {
    if (!open) return null;
    return <div data-testid="mock-icon-picker" />;
  },
}));

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon({ icon }: { icon: string | null; label: string }) {
    return <span data-testid={`service-icon-${icon ?? "none"}`} />;
  },
}));

function setupProductionDataSource() {
  useCatalogStore.getState().clearAll();
  useAuthStore.setState({
    dataSource: createDataSource({
      tenantId: "test-tenant",
      tenantPlan: "pro",
      demo: null,
    }),
  });
}

describe("CatalogPage error message handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps invalid_icon_reference from Axios response.data.detail to i18n key", async () => {
    setupProductionDataSource();

    const axiosError = new Error("Request failed") as Error & {
      response: { data: { detail: string } };
    };
    axiosError.response = { data: { detail: "invalid_icon_reference" } };

    vi.spyOn(api, "get").mockRejectedValueOnce(axiosError);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.catalog.invalid_icon")).toBeInTheDocument();
    });
  });

  it("maps catalog_icon_invalid from error.message to i18n key", async () => {
    setupProductionDataSource();

    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("catalog_icon_invalid"));

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.catalog.invalid_icon")).toBeInTheDocument();
    });
  });

  it("maps catalog_icon_invalid from response.data.detail when error.message is generic", async () => {
    setupProductionDataSource();

    const axiosError = new Error("Something went wrong") as Error & {
      response: { data: { detail: string } };
    };
    axiosError.response = { data: { detail: "catalog_icon_invalid" } };

    vi.spyOn(api, "get").mockRejectedValueOnce(axiosError);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.catalog.invalid_icon")).toBeInTheDocument();
    });
  });

  it("maps service_name_already_exists from error.message", async () => {
    setupProductionDataSource();

    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("service_name_already_exists"));

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.catalog.service_name_exists")).toBeInTheDocument();
    });
  });

  it("falls back to error.message for unmapped errors", async () => {
    setupProductionDataSource();

    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Unknown error"));

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("Unknown error")).toBeInTheDocument();
    });
  });

  it("falls back to i18n key when error has no message", async () => {
    setupProductionDataSource();

    vi.spyOn(api, "get").mockRejectedValueOnce(null);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText("frontend.catalog.error_load_services")).toBeInTheDocument();
    });
  });
});
