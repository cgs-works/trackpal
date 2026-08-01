import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RegionalSettingsSection } from "../regional-settings-section";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
}));

const mockUseAuthStore = vi.fn();
const mockUseSettingsStore = vi.fn();

vi.mock("@/store/auth", () => ({
  useAuthStore: (...args: unknown[]) => mockUseAuthStore(...args),
}));

vi.mock("@/store/settings", () => ({
  useSettingsStore: (...args: unknown[]) => mockUseSettingsStore(...args),
}));

const baseSettingsState = {
  tenantSettings: {
    locale: "en",
    timezone: "UTC",
    country: "VE",
    currency: "VES",
  },
  timezoneOptions: [
    { value: "America/Caracas", label: "Caracas", group: "South America" },
    { value: "UTC", label: "UTC", group: "UTC" },
  ],
  currencyOptions: {
    countries: [
      { code: "VE", currency: "VES" },
      { code: "US", currency: "USD" },
    ],
    currencies: [
      { code: "VES", symbol: "Bs.", minor_units: 2 },
      { code: "USD", symbol: "$", minor_units: 2 },
      { code: "EUR", symbol: "€", minor_units: 2 },
    ],
  },
  loadTenantSettings: vi.fn().mockResolvedValue(undefined),
  loadTimezoneOptions: vi.fn().mockResolvedValue(undefined),
  loadCurrencyOptions: vi.fn().mockResolvedValue(undefined),
  updateTenantSettings: vi.fn().mockResolvedValue({}),
};

describe("RegionalSettingsSection", () => {
  it("renders all four fields for Pro tenant", async () => {
    mockUseAuthStore.mockReturnValue({
      role: "tenant",
      tenantPlan: "pro",
      dataSource: { settings: {} },
    });
    mockUseSettingsStore.mockReturnValue(baseSettingsState);

    render(<RegionalSettingsSection />);

    await waitFor(() => {
      expect(screen.getByText("frontend.my_account.regional.country")).toBeInTheDocument();
    });
    expect(screen.getByText("frontend.profile.language")).toBeInTheDocument();
    expect(screen.getByText("frontend.subscriptions.timezone")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.regional.currency")).toBeInTheDocument();
  });

  it("hides timezone and currency for Starter tenant", async () => {
    mockUseAuthStore.mockReturnValue({
      role: "tenant",
      tenantPlan: "starter",
      dataSource: { settings: {} },
    });
    mockUseSettingsStore.mockReturnValue(baseSettingsState);

    render(<RegionalSettingsSection />);

    await waitFor(() => {
      expect(screen.getByText("frontend.my_account.regional.country")).toBeInTheDocument();
    });
    expect(screen.getByText("frontend.profile.language")).toBeInTheDocument();
    expect(screen.queryByText("frontend.subscriptions.timezone")).not.toBeInTheDocument();
    expect(screen.queryByText("frontend.my_account.regional.currency")).not.toBeInTheDocument();
  });

  it("shows all fields for master support context", async () => {
    mockUseAuthStore.mockReturnValue({
      role: "master",
      tenantPlan: "starter",
      isMasterSupportContext: true,
      dataSource: { settings: {} },
    });
    mockUseSettingsStore.mockReturnValue(baseSettingsState);

    render(<RegionalSettingsSection />);

    await waitFor(() => {
      expect(screen.getByText("frontend.my_account.regional.country")).toBeInTheDocument();
    });
    expect(screen.getByText("frontend.profile.language")).toBeInTheDocument();
    expect(screen.getByText("frontend.subscriptions.timezone")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.regional.currency")).toBeInTheDocument();
  });
});
