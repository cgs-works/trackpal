/**
 * Tests for catalog page plan price input and display (Task 11).
 *
 * Verifies:
 * - Price input in create plan form sends price in payload
 * - Price displayed with tenant currency symbol
 * - Price on request shown when plan has no price
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CatalogPage } from "../catalog-page";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useCatalogStore } from "@/store/catalog";
import { useSettingsStore } from "@/store/settings";
import api from "@/lib/api";
import type { Service, Plan } from "@/features/admin/services/catalog-api";

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
      <span data-testid={`service-icon-${icon ?? "none"}`}>{label}</span>
    );
  },
}));

const mockServices: Service[] = [
  {
    id: "service-1",
    tenant_id: "t1",
    name: "Netflix",
    icon: "simple-icons:netflix",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockPlansWithPrice: Plan[] = [
  {
    id: "plan-1",
    tenant_id: "t1",
    service_id: "service-1",
    name: "Basico",
    price: "12.50",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockPlansNoPrice: Plan[] = [
  {
    id: "plan-2",
    tenant_id: "t1",
    service_id: "service-1",
    name: "Premium",
    price: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const mockTenantSettings = {
  tenant_id: "t1",
  locale: "es",
  timezone: "America/Caracas",
  country: "VE",
  currency: "VES",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockCurrencyOptions = {
  countries: [{ code: "VE", currency: "VES" }],
  currencies: [
    { code: "VES", symbol: "Bs.", minor_units: 2 },
    { code: "USD", symbol: "$", minor_units: 2 },
  ],
};

function setupProductionDataSource() {
  useCatalogStore.getState().clearAll();
  useSettingsStore.setState({
    tenantSettings: mockTenantSettings,
    tenantSettingsLoaded: true,
    currencyOptions: mockCurrencyOptions,
    currencyOptionsLoaded: true,
  });
  useAuthStore.setState({
    dataSource: createDataSource({
      tenantId: "t1",
      tenantPlan: "pro",
      demo: null,
    }),
  });
}

/** Wait for services to load and first service to be auto-selected. */
async function waitForPlansLoaded() {
  await waitFor(() => {
    // The plan form appears when a service is selected
    expect(screen.getByLabelText(/frontend\.catalog\.price/i)).toBeInTheDocument();
  });
}

describe("CatalogPage plan price", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("creates a plan with a price", async () => {
    setupProductionDataSource();
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");

    getSpy.mockImplementation(async (url: string) => {
      if (url === "/catalog/services") return { data: mockServices };
      if (url === "/catalog/services/service-1/plans") return { data: [] };
      return { data: [] };
    });
    postSpy.mockResolvedValue({
      data: {
        id: "plan-new",
        tenant_id: "t1",
        service_id: "service-1",
        name: "Basico",
        price: "12.50",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    });

    render(<CatalogPage />);
    await waitForPlansLoaded();

    const nameInput = screen.getByPlaceholderText("frontend.catalog.new_plan_placeholder");
    const priceInput = screen.getByLabelText("frontend.catalog.price");

    await user.type(nameInput, "Basico");
    await user.type(priceInput, "12.50");

    // The submit button is the icon-only button inside the form (type="submit")
    const form = priceInput.closest("form")!;
    const submitBtn = form.querySelector('button[type="submit"]')!;
    await user.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        "/catalog/services/service-1/plans",
        { name: "Basico", price: "12.50" },
      );
    });
  });

  it("shows the price with the tenant currency symbol", async () => {
    setupProductionDataSource();
    const getSpy = vi.spyOn(api, "get");

    getSpy.mockImplementation(async (url: string) => {
      if (url === "/catalog/services") return { data: mockServices };
      if (url === "/catalog/services/service-1/plans")
        return { data: mockPlansWithPrice };
      return { data: [] };
    });

    render(<CatalogPage />);

    // Check for the currency symbol
    await waitFor(() => {
      const priceElements = screen.getAllByText(/Bs\./);
      expect(priceElements.length).toBeGreaterThanOrEqual(1);
    });
    // "12,50" is the es-VE formatted version of 12.50
    expect(screen.getByText(/12[,.]50/)).toBeInTheDocument();
  });

  it("shows price on request when a plan has no price", async () => {
    setupProductionDataSource();
    const getSpy = vi.spyOn(api, "get");

    getSpy.mockImplementation(async (url: string) => {
      if (url === "/catalog/services") return { data: mockServices };
      if (url === "/catalog/services/service-1/plans")
        return { data: mockPlansNoPrice };
      return { data: [] };
    });

    render(<CatalogPage />);

    await waitFor(() => {
      expect(
        screen.getByText("frontend.catalog.price_on_request"),
      ).toBeInTheDocument();
    });
  });

  it("sends null price when price field is empty", async () => {
    setupProductionDataSource();
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");

    getSpy.mockImplementation(async (url: string) => {
      if (url === "/catalog/services") return { data: mockServices };
      if (url === "/catalog/services/service-1/plans") return { data: [] };
      return { data: [] };
    });
    postSpy.mockResolvedValue({
      data: {
        id: "plan-new",
        tenant_id: "t1",
        service_id: "service-1",
        name: "Sin Precio",
        price: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    });

    render(<CatalogPage />);
    await waitForPlansLoaded();

    await user.type(screen.getByPlaceholderText("frontend.catalog.new_plan_placeholder"), "Sin Precio");
    // Leave price empty

    const form = screen.getByLabelText("frontend.catalog.price").closest("form")!;
    const submitBtn = form.querySelector('button[type="submit"]')!;
    await user.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        "/catalog/services/service-1/plans",
        { name: "Sin Precio", price: null },
      );
    });
  });

  it("sends price in edit plan payload", async () => {
    setupProductionDataSource();
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const putSpy = vi.spyOn(api, "put");

    getSpy.mockImplementation(async (url: string) => {
      if (url === "/catalog/services") return { data: mockServices };
      if (url === "/catalog/services/service-1/plans")
        return { data: mockPlansNoPrice };
      return { data: [] };
    });
    putSpy.mockResolvedValue({
      data: { ...mockPlansNoPrice[0], name: "Premium", price: "25.00" },
    });

    render(<CatalogPage />);

    await waitFor(() =>
      expect(screen.getByText("Premium")).toBeInTheDocument(),
    );

    // Find the plan card containing "Premium" and click its edit button
    const planCard = screen.getByText("Premium").closest(".rounded-lg.border")!;
    const editBtn = within(planCard as HTMLElement).getByRole("button", { name: /frontend\.catalog\.rename/i });
    await user.click(editBtn);

    // Wait for dialog to open
    const dialog = await screen.findByRole("dialog");

    // The name input inside the dialog
    const dialogNameInput = within(dialog).getByLabelText("frontend.common.name");
    expect(dialogNameInput).toHaveValue("Premium");

    // Type price in the edit dialog
    const dialogPriceInput = within(dialog).getByLabelText("frontend.catalog.price");
    await user.clear(dialogPriceInput);
    await user.type(dialogPriceInput, "25.00");

    // Submit via the save button in the dialog
    const saveBtn = within(dialog).getByRole("button", { name: /frontend\.catalog\.rename/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(putSpy).toHaveBeenCalledWith(
        "/catalog/services/service-1/plans/plan-2",
        { name: "Premium", price: "25.00" },
      );
    });
  });
});
