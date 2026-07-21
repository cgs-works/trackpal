import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "../settings-page";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

const mockUseAuthStore = vi.fn();

vi.mock("@/store/auth", () => ({
  useAuthStore: (...args: unknown[]) => mockUseAuthStore(...args),
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
vi.mock("../whatsapp-link-section", () => ({ WhatsappLinkSection: () => <div>whatsapp link section</div> }));

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("unauthenticated/guide", () => {
    it("starts with no selected category and shows the guide message", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      render(<SettingsPage />);

      expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
      expect(screen.getByText("frontend.settings.guide_description")).toBeInTheDocument();
      expect(screen.queryByText("access control section")).not.toBeInTheDocument();
      await waitFor(() => expect(screen.getByText("frontend.settings.title")).toBeInTheDocument());
    });

    it("opens one category in the active panel and cancel closes it", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getAllByText("frontend.access_control.section_title")[0]);
      expect(screen.getByText("access control section")).toBeInTheDocument();
      expect(screen.getByLabelText("frontend.settings.active_panel")).toHaveAttribute(
        "data-help-id",
        "admin.settings.access-control",
      );
      expect(screen.queryByText("frontend.settings.guide_title")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "frontend.settings.cancel" }));
      expect(screen.getByText("frontend.settings.guide_title")).toBeInTheDocument();
      expect(screen.queryByText("access control section")).not.toBeInTheDocument();
    });

    it("opens category selection from the mobile sheet trigger", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByRole("button", { name: "frontend.settings.select_category" }));

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getAllByText("frontend.profile.language").length).toBeGreaterThan(0);
    });
  });

  describe("WhatsApp section visibility", () => {
    it("shows WhatsApp section for Pro tenant admin", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      render(<SettingsPage />);

      // WhatsApp section title should be in the sidebar
      expect(screen.getByText("frontend.whatsapp_link.section_title")).toBeInTheDocument();
    });

    it("shows WhatsApp section for starter tenant admin without exposing Pro-only settings", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "starter",
        isMasterSupportContext: false,
      });

      render(<SettingsPage />);

      expect(screen.getByText("frontend.whatsapp_link.section_title")).toBeInTheDocument();
      expect(screen.queryByText("frontend.subscriptions.reminder_settings_title")).not.toBeInTheDocument();
      expect(screen.queryByText("frontend.subscriptions.timezone")).not.toBeInTheDocument();
      expect(screen.queryByText("frontend.public_api.section_title")).not.toBeInTheDocument();
    });

    it("shows WhatsApp section for master support context even with starter plan", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "master",
        tenantPlan: "starter",
        isMasterSupportContext: true,
      });

      render(<SettingsPage />);

      expect(screen.getByText("frontend.whatsapp_link.section_title")).toBeInTheDocument();
    });

    it("renders WhatsappLinkSection when WhatsApp category is selected", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByText("frontend.whatsapp_link.section_title"));

      expect(screen.getByText("whatsapp link section")).toBeInTheDocument();
    });

    it("exposes contextual targets for Pro reminder and timezone categories", async () => {
      mockUseAuthStore.mockReturnValue({
        role: "tenant",
        tenantPlan: "pro",
        isMasterSupportContext: false,
      });

      const user = userEvent.setup();
      render(<SettingsPage />);

      await user.click(screen.getByText("frontend.subscriptions.reminder_settings_title"));
      expect(screen.getByLabelText("frontend.settings.active_panel")).toHaveAttribute(
        "data-help-id",
        "admin.settings.reminders",
      );

      await user.click(screen.getByRole("button", { name: "frontend.settings.cancel" }));
      await user.click(screen.getByText("frontend.subscriptions.timezone"));
      expect(screen.getByLabelText("frontend.settings.active_panel")).toHaveAttribute(
        "data-help-id",
        "admin.settings.timezone",
      );
    });
  });
});
