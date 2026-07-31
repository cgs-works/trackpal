import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useSettingsStore } from "@/store/settings";
import { MailboxSection } from "../mailbox-section";

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
    connectGmail: (...args: unknown[]) => mockConnectGmail(...args),
  };
});

describe("MailboxSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    mockConnectGmail.mockResolvedValue({
      id: "m1",
      mailbox_email: "test@gmail.com",
      status: "connected",
    });
    useAuthStore.setState({
      dataSource: createDataSource({ tenantId: null, tenantPlan: null, demo: null }),
    });
    useSettingsStore.setState({
      mailbox: null,
      mailboxLoaded: true,
      mailboxInFlight: null,
    });
  });

  it("shows connected mailbox with email and status", () => {
    useSettingsStore.setState({
      mailbox: {
        id: "m1",
        tenant_id: "t1",
        mailbox_email: "admin@gmail.com",
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
    // No method label
    expect(screen.queryByText("frontend.mailbox.method_google_connection")).not.toBeInTheDocument();
    expect(screen.queryByText("frontend.mailbox.method_app_password")).not.toBeInTheDocument();
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
