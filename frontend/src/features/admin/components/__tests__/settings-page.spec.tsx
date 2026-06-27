import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "../settings-page";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    role: "tenant",
    tenantPlan: "pro",
    isMasterSupportContext: false,
  }),
}));

vi.mock("../../services/settings-api", () => ({
  getProfile: vi.fn().mockResolvedValue({
    id: "tenant-1",
    full_name: "Demo Tenant",
    email: "demo@example.com",
    phone: "12015550000",
  }),
}));

vi.mock("../reminder-settings-section", () => ({ ReminderSettingsSection: () => <div>reminders section</div> }));
vi.mock("../locale-section", () => ({ LocaleSection: () => <div>locale section</div> }));
vi.mock("../timezone-section", () => ({ TimezoneSection: () => <div>timezone section</div> }));
vi.mock("../public-api-section", () => ({ PublicApiSection: () => <div>public api section</div> }));
vi.mock("../code-services-section", () => ({ CodeServicesSection: () => <div>code services section</div> }));
vi.mock("../mailbox-section", () => ({ MailboxSection: () => <div>mailbox section</div> }));
vi.mock("../access-control-section", () => ({ AccessControlSection: () => <div>access control section</div> }));
vi.mock("../profile-section", () => ({ ProfileSection: () => <div>profile section</div> }));
vi.mock("../password-section", () => ({ PasswordSection: () => <div>password section</div> }));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with no selected category and shows the guide message", async () => {
    render(<SettingsPage />);

    expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
    expect(screen.getByText("frontend.settings.guide_description")).toBeInTheDocument();
    expect(screen.queryByText("access control section")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("frontend.settings.title")).toBeInTheDocument());
  });

  it("opens one category in the active panel and cancel closes it", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(screen.getAllByText("frontend.access_control.section_title")[0]);
    expect(screen.getByText("access control section")).toBeInTheDocument();
    expect(screen.queryByText("frontend.settings.guide_title")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.settings.cancel" }));
    expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
    expect(screen.queryByText("access control section")).not.toBeInTheDocument();
  });

  it("opens category selection from the mobile sheet trigger", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);

    await user.click(screen.getByRole("button", { name: "frontend.settings.select_category" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getAllByText("frontend.profile.language").length).toBeGreaterThan(0);
  });
});
