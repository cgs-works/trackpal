import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useSettingsStore } from "@/store/settings";
import { MailboxSection } from "../mailbox-section";

const mockStartGoogleOAuth = vi.fn();
const mockConnectGmail = vi.fn();

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
    startGoogleOAuth: (...args: unknown[]) => mockStartGoogleOAuth(...args),
    connectGmail: (...args: unknown[]) => mockConnectGmail(...args),
  };
});

class BroadcastChannelStub {
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

describe("MailboxSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    Object.defineProperty(globalThis, "BroadcastChannel", {
      configurable: true,
      value: BroadcastChannelStub,
    });
    vi.spyOn(window, "open").mockImplementation(() => null);
    mockStartGoogleOAuth.mockResolvedValue({ auth_url: "https://accounts.google.com/oauth" });
    mockConnectGmail.mockResolvedValue({ id: "m1", mailbox_email: "test@gmail.com", auth_method: "app_password", status: "connected" });
    useAuthStore.setState({
      dataSource: createDataSource({ tenantId: null, tenantPlan: null, demo: null }),
    });
    useSettingsStore.setState({
      mailbox: null,
      mailboxLoaded: true,
      mailboxInFlight: null,
    });
  });

  it("hides OAuth disclosure when flag is false/missing", () => {
    render(<MailboxSection />);
    expect(screen.queryByText(/OAuth/i)).not.toBeInTheDocument();
    expect(screen.queryByText("frontend.mailbox.use_google_connection")).not.toBeInTheDocument();
  });

  it("shows Google Connection option when flag is exact true", () => {
    vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", "true");
    render(<MailboxSection />);
    expect(screen.getByText("frontend.mailbox.use_google_connection")).toBeInTheDocument();
  });

  it("shows connected OAuth mailbox even when flag is false", () => {
    useSettingsStore.setState({
      mailbox: {
        id: "m1",
        tenant_id: "t1",
        mailbox_email: "admin@gmail.com",
        auth_method: "oauth",
        status: "connected",
        last_connection_test_at: null,
        last_connection_error: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
      mailboxLoaded: true,
    });
    render(<MailboxSection />);
    expect(screen.getByText("admin@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("frontend.mailbox.status_connected")).toBeInTheDocument();
  });

  it("displays correct method label for oauth mailbox", () => {
    useSettingsStore.setState({
      mailbox: {
        id: "m1",
        tenant_id: "t1",
        mailbox_email: "admin@gmail.com",
        auth_method: "oauth",
        status: "connected",
        last_connection_test_at: null,
        last_connection_error: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
      mailboxLoaded: true,
    });
    render(<MailboxSection />);
    expect(screen.getByText("frontend.mailbox.method_google_connection")).toBeInTheDocument();
    expect(screen.queryByText(/IMAP/i)).not.toBeInTheDocument();
  });

  it("displays correct method label for app_password mailbox", () => {
    useSettingsStore.setState({
      mailbox: {
        id: "m1",
        tenant_id: "t1",
        mailbox_email: "admin@gmail.com",
        auth_method: "app_password",
        status: "connected",
        last_connection_test_at: null,
        last_connection_error: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
      mailboxLoaded: true,
    });
    render(<MailboxSection />);
    expect(screen.getByText("frontend.mailbox.method_app_password")).toBeInTheDocument();
    expect(screen.queryByText(/IMAP/i)).not.toBeInTheDocument();
  });

  it("shows the Gmail setup assistant when no mailbox is configured", () => {
    render(<MailboxSection />);
    expect(
      screen.getByText("frontend.mailbox.app_password_step_title"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "frontend.mailbox.open_google" }),
    ).toHaveAttribute("href", "https://myaccount.google.com/apppasswords");
  });

  it("requires consent before starting OAuth when flag is true", async () => {
    vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", "true");
    const user = userEvent.setup();
    render(<MailboxSection />);

    const useGoogleBtn = screen.getByText("frontend.mailbox.use_google_connection");
    await user.click(useGoogleBtn);

    expect(screen.getByText("frontend.mailbox.oauth_consent_title")).toBeInTheDocument();
    const consent = screen.getByRole("checkbox", {
      name: "frontend.mailbox.oauth_consent_checkbox",
    });
    const startBtn = screen.getByRole("button", {
      name: "frontend.mailbox.continue_google",
    });
    expect(consent).not.toBeChecked();
    expect(startBtn).toBeDisabled();

    await user.click(consent);
    expect(startBtn).toBeEnabled();

    await user.click(startBtn);
    await waitFor(() => expect(mockStartGoogleOAuth).toHaveBeenCalled());
    expect(window.open).toHaveBeenCalledWith(
      "https://accounts.google.com/oauth",
      "_blank",
      "width=500,height=600",
    );
  });
});
