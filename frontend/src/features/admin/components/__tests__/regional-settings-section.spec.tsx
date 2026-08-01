import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegionalSettingsSection } from "../regional-settings-section";

const loadCatalog = vi.fn().mockResolvedValue(undefined);

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
  loadCatalog: (...args: unknown[]) => loadCatalog(...args),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: ReactNode;
  }) => (
    <select
      aria-label="locale"
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
    >
      {children}
    </select>
  ),
  SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: ReactNode }) => (
    <option value={value}>{children}</option>
  ),
  SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  SelectValue: () => null,
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
  beforeEach(() => {
    vi.clearAllMocks();
    baseSettingsState.updateTenantSettings.mockResolvedValue({ locale: "es" });
    loadCatalog.mockResolvedValue(undefined);
  });

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

  it("omits timezone and currency from payload for Starter tenant", async () => {
    const user = userEvent.setup();

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

    await user.click(screen.getByRole("button", { name: "frontend.profile.save" }));

    await waitFor(() => {
      expect(baseSettingsState.updateTenantSettings).toHaveBeenCalledTimes(1);
    });

    const payload = baseSettingsState.updateTenantSettings.mock.calls[0][0];
    expect(payload).not.toHaveProperty("timezone");
    expect(payload).not.toHaveProperty("currency");
    expect(payload).toHaveProperty("locale");
    expect(payload).toHaveProperty("country");
  });

  it("includes timezone and currency in payload for Pro tenant", async () => {
    const user = userEvent.setup();

    mockUseAuthStore.mockReturnValue({
      role: "tenant",
      tenantPlan: "pro",
      dataSource: { settings: {} },
    });
    mockUseSettingsStore.mockReturnValue(baseSettingsState);

    render(<RegionalSettingsSection />);

    await waitFor(() => {
      expect(screen.getByText("frontend.profile.language")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "frontend.profile.save" }));

    await waitFor(() => {
      expect(baseSettingsState.updateTenantSettings).toHaveBeenCalledTimes(1);
    });

    const payload = baseSettingsState.updateTenantSettings.mock.calls[0][0];
    expect(payload).toHaveProperty("timezone");
    expect(payload).toHaveProperty("currency");
  });

  it("loads catalog in demo mode when locale changes", async () => {
    const user = userEvent.setup();

    mockUseAuthStore.mockReturnValue({
      role: "tenant",
      tenantPlan: "pro",
      dataSource: { mode: "demo", settings: { mode: "demo-settings" } },
    });
    mockUseSettingsStore.mockReturnValue({
      ...baseSettingsState,
      tenantSettings: { ...baseSettingsState.tenantSettings, locale: "en" },
    });

    render(<RegionalSettingsSection />);

    await waitFor(() => {
      expect(screen.getByText("frontend.profile.language")).toBeInTheDocument();
    });

    const localeSelect = screen.getByRole("combobox", { name: "locale" });
    await user.selectOptions(localeSelect, "es");
    await user.click(screen.getByRole("button", { name: "frontend.profile.save" }));

    await waitFor(() => {
      expect(baseSettingsState.updateTenantSettings).toHaveBeenCalledWith(
        expect.objectContaining({ locale: "es" }),
        expect.objectContaining({ mode: "demo-settings" }),
      );
      expect(loadCatalog).toHaveBeenCalledWith("es");
    });
  });
});
