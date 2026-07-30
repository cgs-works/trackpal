import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useSettingsStore } from "@/store/settings";
import { MailboxSection } from "../mailbox-section";

const mockStartOAuth = vi.fn();

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

vi.mock("@/features/admin/services/settings-api", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("@/features/admin/services/settings-api")
  >();
  return {
    ...actual,
    startOAuth: (...args: unknown[]) => mockStartOAuth(...args),
  };
});

class BroadcastChannelStub {
  onmessage: ((event: MessageEvent) => void) | null = null;

  close() {}
}

describe("MailboxSection OAuth consent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(globalThis, "BroadcastChannel", {
      configurable: true,
      value: BroadcastChannelStub,
    });
    vi.spyOn(window, "open").mockImplementation(() => null);
    mockStartOAuth.mockResolvedValue({ auth_url: "https://accounts.google.com/oauth" });
    useAuthStore.setState({
      dataSource: createDataSource({ tenantId: null, tenantPlan: null, demo: null }),
    });
    useSettingsStore.setState({
      mailbox: null,
      mailboxLoaded: true,
      mailboxInFlight: null,
    });
  });

  it("requires affirmative consent before starting Google OAuth", async () => {
    const user = userEvent.setup();
    render(<MailboxSection />);

    expect(
      await screen.findByText("frontend.mailbox.oauth_consent_title"),
    ).toBeInTheDocument();
    expect(screen.getByText("frontend.mailbox.oauth_consent_data")).toBeInTheDocument();
    expect(screen.getByText("frontend.mailbox.oauth_consent_transfer")).toBeInTheDocument();
    expect(screen.getByText("frontend.mailbox.oauth_consent_storage")).toBeInTheDocument();

    const consent = screen.getByRole("checkbox", {
      name: "frontend.mailbox.oauth_consent_checkbox",
    });
    const continueButton = screen.getByRole("button", {
      name: "frontend.mailbox.continue_google",
    });

    expect(consent).not.toBeChecked();
    expect(continueButton).toBeDisabled();

    await user.click(consent);
    expect(continueButton).toBeEnabled();

    await user.click(continueButton);

    await waitFor(() => expect(mockStartOAuth).toHaveBeenCalledWith("google"));
    expect(window.open).toHaveBeenCalledWith(
      "https://accounts.google.com/oauth",
      "_blank",
      "width=500,height=600",
    );
  });

  it("requires fresh consent after changing OAuth provider", async () => {
    const user = userEvent.setup();
    render(<MailboxSection />);

    const consent = await screen.findByRole("checkbox", {
      name: "frontend.mailbox.oauth_consent_checkbox",
    });
    await user.click(consent);
    expect(consent).toBeChecked();

    await user.click(
      screen.getByRole("button", {
        name: /frontend\.mailbox\.connect_microsoft/,
      }),
    );

    expect(consent).not.toBeChecked();
    expect(
      screen.getByRole("button", {
        name: "frontend.mailbox.continue_microsoft",
      }),
    ).toBeDisabled();
  });
});
