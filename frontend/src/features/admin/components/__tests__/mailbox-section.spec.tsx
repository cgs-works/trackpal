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

import { toast } from "sonner";

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

  it("shows Google Connection option inside assistant when flag is exact true", () => {
    vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", "true");
    render(<MailboxSection />);
    // The "Use Google Connection" button is now inside GmailSetupAssistant
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

  it("shows safe generic error message for unknown error codes", async () => {
    const user = userEvent.setup();
    mockConnectGmail.mockRejectedValueOnce({
      response: { data: { detail: "some_unexpected_error_code" } },
    });
    render(<MailboxSection />);

    // Navigate to credentials
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.have_app_password",
      }),
    );

    // Fill and submit
    await user.type(
      screen.getByLabelText("frontend.mailbox.google_email"),
      "test@gmail.com",
    );
    await user.type(
      screen.getByLabelText("frontend.mailbox.app_password"),
      "test-password",
    );
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.connect_gmail",
      }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("frontend.mailbox.error_save");
    });
  });
});
