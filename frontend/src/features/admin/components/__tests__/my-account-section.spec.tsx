import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { createDataSource } from "@/lib/data-source";
import { MyAccountSection } from "../my-account-section";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
}));

const mockUseAuthStore = vi.fn();

vi.mock("@/store/auth", () => ({
  useAuthStore: (...args: unknown[]) => mockUseAuthStore(...args),
}));

vi.mock("../profile-section", () => ({
  ProfileSection: ({ onSave }: { onSave?: () => void }) => (
    <div data-testid="profile-section" data-has-onsave={String(!!onSave)}>
      profile section
    </div>
  ),
}));

vi.mock("../password-section", () => ({
  PasswordSection: () => <div data-testid="password-section">password section</div>,
}));

const mockProfile = {
  id: "tenant-1",
  full_name: "Demo Tenant",
  email: "demo@example.com",
  phone: "12015550000",
  role: "tenant",
  username: "tenant",
  name: null,
  tenant_id: null,
  tenant_name: null,
  client_prefix: null,
  locale: null,
  timezone: null,
  is_active: true,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("MyAccountSection", () => {
  it("renders Profile, Security, and Data tabs for Tenant Admin", () => {
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: false,
    });

    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    expect(screen.getByText("frontend.my_account.tab_profile")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.tab_security")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.tab_data")).toBeInTheDocument();
  });

  it("renders only Profile and Data tabs for Master Support Context", () => {
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: true,
    });

    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    expect(screen.getByText("frontend.my_account.tab_profile")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.tab_data")).toBeInTheDocument();
    expect(screen.queryByText("frontend.my_account.tab_security")).not.toBeInTheDocument();
  });

  it("shows ProfileSection in the Profile tab by default", () => {
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: false,
    });

    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    expect(screen.getByTestId("profile-section")).toBeInTheDocument();
  });

  it("shows Data empty state with icon and description after clicking the tab", async () => {
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: false,
    });

    const user = userEvent.setup();
    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    await user.click(screen.getByText("frontend.my_account.tab_data"));

    expect(screen.getByText("frontend.my_account.data_empty_title")).toBeInTheDocument();
    expect(screen.getByText("frontend.my_account.data_empty_description")).toBeInTheDocument();
  });

  it("keeps Demo export and deletion actions visible but unavailable without HTTP calls", async () => {
    const metadata = {
      tenantId: "demo-account-settings",
      name: "Demo Account",
      plan: "starter" as const,
      status: "active" as const,
      activatedAt: "2026-07-24T12:00:00.000Z",
      expiresAt: "2026-07-26T12:00:00.000Z",
      credentialVersion: 1,
      serverTime: "2026-07-25T12:00:00.000Z",
    };
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: false,
      dataSource: createDataSource({
        tenantId: metadata.tenantId,
        tenantPlan: metadata.plan,
        demo: metadata,
      }),
    });

    const user = userEvent.setup();
    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    await user.click(screen.getByText("frontend.my_account.tab_data"));

    expect(screen.getByText("frontend.my_account.demo_data_title")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.my_account.data_empty_action" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "frontend.my_account.danger_delete_button" })).toBeDisabled();
    expect(getSpy).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();
  });

  it("passes an onSave handler to ProfileSection when in Master Support Context", () => {
    mockUseAuthStore.mockReturnValue({
      isMasterSupportContext: true,
    });

    render(
      <MyAccountSection profile={mockProfile} onProfileUpdate={vi.fn()} />,
    );

    const profileSection = screen.getByTestId("profile-section");
    expect(profileSection).toHaveAttribute("data-has-onsave", "true");
  });
});
