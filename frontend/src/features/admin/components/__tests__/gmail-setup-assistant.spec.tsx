import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    vi.unstubAllEnvs();
  });

  it("renders app-password instructions directly without method selector", () => {
    render(<GmailSetupAssistant onConnect={vi.fn()} />);

    expect(
      screen.getByText("frontend.mailbox.app_password_step_title"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "frontend.mailbox.open_google" }),
    ).toHaveAttribute("href", "https://myaccount.google.com/apppasswords");
    // No checkbox (no OAuth consent) and no method selector
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(
      screen.queryByText("frontend.mailbox.use_google_connection"),
    ).not.toBeInTheDocument();
  });

  it("guides the user from instructions to credentials", async () => {
    const user = userEvent.setup();
    render(<GmailSetupAssistant onConnect={vi.fn()} />);

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
    render(<GmailSetupAssistant onConnect={connect} />);

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
    render(<GmailSetupAssistant onConnect={connect} />);

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
    render(<GmailSetupAssistant onConnect={vi.fn()} />);

    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.view_tutorial",
      }),
    );

    expect(mockRequestContextualHelp).toHaveBeenCalledWith(HELP_TARGETS.mailbox);
  });

  it("hides tutorial action when private help is disabled", () => {
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");
    render(<GmailSetupAssistant onConnect={vi.fn()} />);

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

  it("allows going back from credentials to instructions", async () => {
    const user = userEvent.setup();
    render(<GmailSetupAssistant onConnect={vi.fn()} />);

    // Navigate to credentials
    await user.click(
      screen.getByRole("button", {
        name: "frontend.mailbox.have_app_password",
      }),
    );
    expect(
      screen.getByLabelText("frontend.mailbox.google_email"),
    ).toBeInTheDocument();

    // Click back
    await user.click(screen.getByText(/frontend\.mailbox\.back/));

    // Back to instructions
    expect(
      screen.getByText("frontend.mailbox.app_password_step_title"),
    ).toBeInTheDocument();
  });
});
