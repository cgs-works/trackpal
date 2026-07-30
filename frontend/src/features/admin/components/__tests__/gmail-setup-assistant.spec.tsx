import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { isGmailOAuthConnectEnabled } from "@/features/admin/mailbox-config";

// ── Release-gate tests ──────────────────────────────────────

describe("isGmailOAuthConnectEnabled", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([undefined, "", "false", "TRUE", "1"])(
    "keeps Gmail OAuth hidden for %s",
    (value) => {
      vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", value as string);
      expect(isGmailOAuthConnectEnabled()).toBe(false);
    },
  );

  it("enables Gmail OAuth only for exact true", () => {
    vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", "true");
    expect(isGmailOAuthConnectEnabled()).toBe(true);
  });
});

// ── GmailSetupAssistant component tests ──────────────────────

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("@/features/help/contextual-help", () => ({
  requestContextualHelp: vi.fn(),
}));

vi.mock("@/features/help/help-targets", () => ({
  HELP_TARGETS: { mailbox: "admin.settings.mailbox" },
}));

import { GmailSetupAssistant } from "../gmail-setup-assistant";
import { requestContextualHelp } from "@/features/help/contextual-help";
import { HELP_TARGETS } from "@/features/help/help-targets";

const mockRequestContextualHelp = vi.mocked(requestContextualHelp);

describe("GmailSetupAssistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("guides the user from app-password instructions to credentials", async () => {
    const user = userEvent.setup();
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    // Step 1: Instructions
    expect(
      screen.getByText("frontend.mailbox.app_password_step_title"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "frontend.mailbox.open_google" }),
    ).toHaveAttribute("href", "https://myaccount.google.com/apppasswords");
    expect(screen.queryByText("OAuth")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Microsoft|Outlook|IMAP/i),
    ).not.toBeInTheDocument();

    // Navigate to credentials
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.have_app_password",
      }),
    );
    expect(
      screen.getByLabelText("frontend.mailbox.google_email"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("frontend.mailbox.app_password"),
    ).toBeInTheDocument();
  });

  it("submits app-password credentials and calls onConnect", async () => {
    const user = userEvent.setup();
    const connect = vi.fn().mockResolvedValue(true);
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={connect}
        onStartOAuth={vi.fn()}
      />,
    );

    // Navigate to credentials
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.have_app_password",
      }),
    );

    // Fill form
    await user.type(
      screen.getByLabelText("frontend.mailbox.google_email"),
      "business@example.com",
    );
    await user.type(
      screen.getByLabelText("frontend.mailbox.app_password"),
      "abcd efgh ijkl mnop",
    );

    // Submit
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.connect_gmail",
      }),
    );

    expect(connect).toHaveBeenCalledWith({
      mailbox_email: "business@example.com",
      app_password: "abcd efgh ijkl mnop",
    });
  });

  it("clears app-password on failure but keeps email", async () => {
    const user = userEvent.setup();
    const connect = vi.fn().mockResolvedValue(false);
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={connect}
        onStartOAuth={vi.fn()}
      />,
    );

    // Navigate to credentials
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.have_app_password",
      }),
    );

    // Fill form
    await user.type(
      screen.getByLabelText("frontend.mailbox.google_email"),
      "business@example.com",
    );
    const passwordField = screen.getByLabelText("frontend.mailbox.app_password");
    await user.type(passwordField, "abcd efgh ijkl mnop");

    // Submit
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.connect_gmail",
      }),
    );

    await waitFor(() => {
      // Email stays
      expect(screen.getByLabelText("frontend.mailbox.google_email")).toHaveValue(
        "business@example.com",
      );
      // Password cleared
      expect(passwordField).toHaveValue("");
    });
  });

  it("calls requestContextualHelp when View full tutorial is clicked", async () => {
    const user = userEvent.setup();
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.view_tutorial",
      }),
    );

    expect(mockRequestContextualHelp).toHaveBeenCalledWith(HELP_TARGETS.mailbox);
  });

  it("hides tutorial action when private help is disabled", () => {
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", {
        name: "frontend.mailbox.view_tutorial",
      }),
    ).not.toBeInTheDocument();
    // But the Google link remains
    expect(
      screen.getByRole("link", { name: "frontend.mailbox.open_google" }),
    ).toBeInTheDocument();
  });

  it("hides OAuth path when oauthConnectEnabled is false", () => {
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={false}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    expect(screen.queryByText(/OAuth/i)).not.toBeInTheDocument();
  });

  // ── OAuth path inside the assistant ────────────────────────

  it("shows two-option selector when oauthConnectEnabled is true", () => {
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={true}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "frontend.mailbox.use_google_connection" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "frontend.mailbox.have_app_password" }),
    ).toBeInTheDocument();
  });

  it("navigates to OAuth consent flow and requires consent before calling onStartOAuth", async () => {
    const user = userEvent.setup();
    const onStartOAuth = vi.fn().mockResolvedValue(undefined);
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={true}
        onConnect={vi.fn()}
        onStartOAuth={onStartOAuth}
      />,
    );

    // Click "Use Google Connection"
    await user.click(
      screen.getByRole("button", { name: "frontend.mailbox.use_google_connection" }),
    );

    // Consent screen visible
    expect(screen.getByText("frontend.mailbox.oauth_consent_title")).toBeInTheDocument();
    const consent = screen.getByRole("checkbox", {
      name: "frontend.mailbox.oauth_consent_checkbox",
    });
    const startBtn = screen.getByRole("button", {
      name: "frontend.mailbox.continue_google",
    });
    expect(consent).not.toBeChecked();
    expect(startBtn).toBeDisabled();

    // Accept consent
    await user.click(consent);
    expect(startBtn).toBeEnabled();

    // Start OAuth
    await user.click(startBtn);
    expect(onStartOAuth).toHaveBeenCalledTimes(1);
  });

  it("allows going back from OAuth consent to the two-option selector", async () => {
    const user = userEvent.setup();
    render(
      <GmailSetupAssistant
        oauthConnectEnabled={true}
        onConnect={vi.fn()}
        onStartOAuth={vi.fn()}
      />,
    );

    // Enter OAuth consent
    await user.click(
      screen.getByRole("button", { name: "frontend.mailbox.use_google_connection" }),
    );
    expect(screen.getByText("frontend.mailbox.oauth_consent_title")).toBeInTheDocument();

    // Click back
    await user.click(screen.getByText(/frontend\.mailbox\.back/));

    // Back to selector
    expect(
      screen.getByRole("button", { name: "frontend.mailbox.use_google_connection" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "frontend.mailbox.have_app_password" }),
    ).toBeInTheDocument();
  });
});
