import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleSection } from "../locale-section";
import { loadCatalog } from "@/i18n";

const state = vi.hoisted(() => ({
  loadTenantSettings: vi.fn(),
  updateTenantSettings: vi.fn(),
  settings: { mode: "demo-settings" },
  tenantSettings: { locale: "en" },
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

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  loadCatalog: vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    dataSource: { mode: "demo", settings: state.settings },
  }),
}));

vi.mock("@/store/settings", () => ({
  useSettingsStore: () => ({
    tenantSettings: state.tenantSettings,
    loadTenantSettings: state.loadTenantSettings,
    updateTenantSettings: state.updateTenantSettings,
  }),
}));

describe("LocaleSection Demo behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.loadTenantSettings.mockResolvedValue(undefined);
    state.updateTenantSettings.mockResolvedValue({ locale: "es" });
    vi.mocked(loadCatalog).mockResolvedValue(undefined);
  });

  it("loads the selected catalog while keeping locale persistence browser-local", async () => {
    const user = userEvent.setup();
    render(<LocaleSection />);

    await user.selectOptions(screen.getByRole("combobox", { name: "locale" }), "es");
    await user.click(screen.getByRole("button", { name: "frontend.profile.save" }));

    await waitFor(() => {
      expect(state.updateTenantSettings).toHaveBeenCalledWith(
        { locale: "es" },
        state.settings,
      );
      expect(loadCatalog).toHaveBeenCalledWith("es");
    });
  });
});
