import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContextualHelpSheet } from "../contextual-help-sheet";
import { getHelpIndex, getHelpTopic } from "../../services/help-api";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => (
    <a href={to} {...props}>{children}</a>
  ),
  Navigate: () => null,
}));

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("../../services/help-api", () => ({
  getHelpIndex: vi.fn(),
  getHelpTopic: vi.fn(),
  searchHelp: vi.fn(),
  getUnseenHelpTour: vi.fn(),
  replayHelpTour: vi.fn(),
  acknowledgeHelpTour: vi.fn(),
}));

const topic = {
  id: "tenant-admin.profile",
  title: "Profile",
  summary: "Profile guidance",
  module: "settings",
  route: "/admin/settings",
  order: 40,
  help_targets: ["admin.settings.profile"],
  safe_navigation: { route: "/admin/settings", settings_category: "profile" },
  body: "# Profile\n\nProfile guidance body.",
};

describe("ContextualHelpSheet", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "true");
    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-common-modules-1",
      frontend_target_contract_version: "2",
      locale: "en",
      topics: [
        {
          id: topic.id,
          title: topic.title,
          summary: topic.summary,
          module: topic.module,
          route: topic.route,
          order: topic.order,
          help_targets: topic.help_targets,
          safe_navigation: topic.safe_navigation,
        },
      ],
    });
    vi.mocked(getHelpTopic).mockResolvedValue(topic);
  });

  it("returns null when private help is disabled without violating hooks rules", () => {
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");
    const { container } = render(<ContextualHelpSheet />);
    expect(container.innerHTML).toBe("");
  });

  it("does not crash when toggling help enabled → disabled (hooks stability)", () => {
    const { rerender, unmount } = render(<ContextualHelpSheet />);
    expect(screen.getByRole("button", { name: "frontend.help.about_screen" })).toBeInTheDocument();

    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");
    rerender(<ContextualHelpSheet />);
    expect(screen.queryByRole("button", { name: "frontend.help.about_screen" })).not.toBeInTheDocument();

    unmount();
  });

  it("opens only the Client topic for a Client target", async () => {
    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-client-manual-1",
      frontend_target_contract_version: "2",
      locale: "en",
      topics: [
        {
          id: "client.profile",
          title: "Client Profile",
          summary: "Client profile guidance",
          module: "profile",
          route: "/client/profile",
          order: 20,
          help_targets: ["client.profile"],
          safe_navigation: { route: "/client/profile", settings_category: null },
        },
      ],
    });
    vi.mocked(getHelpTopic).mockResolvedValue({
      id: "client.profile",
      title: "Client Profile",
      summary: "Client profile guidance",
      module: "profile",
      route: "/client/profile",
      order: 20,
      help_targets: ["client.profile"],
      safe_navigation: { route: "/client/profile", settings_category: null },
      body: "# Client Profile\n\nClient-only guidance.",
    });

    render(
      <>
        <section data-help-id="client.profile">
          <p>Client profile</p>
        </section>
        <ContextualHelpSheet audience="client" />
      </>,
    );

    await userEvent.click(screen.getByRole("button", { name: "frontend.help.about_screen" }));
    await waitFor(() => expect(screen.getByText("Client-only guidance.")).toBeInTheDocument());
    expect(getHelpTopic).toHaveBeenCalledWith("client.profile");
    expect(screen.getByRole("link")).toHaveAttribute("href", "/client/profile");
  });

  it("opens the exact authorized topic without losing local form state", async () => {
    const user = userEvent.setup();
    render(
      <>
        <section data-help-id="admin.settings.profile">
          <label htmlFor="business-name">Business name</label>
          <input id="business-name" defaultValue="Unsaved business" />
        </section>
        <ContextualHelpSheet />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "frontend.help.about_screen" }));
    await waitFor(() => expect(screen.getByText("Profile guidance body.")).toBeInTheDocument());
    expect(getHelpTopic).toHaveBeenCalledWith("tenant-admin.profile");
    expect(screen.getByLabelText("Business name")).toHaveValue("Unsaved business");

    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "frontend.help.about_screen" })).toHaveFocus();
  });

  it("opens a requested authorized target without unmounting local state", async () => {
    const { requestContextualHelp } = await import("../../contextual-help");
    const { HELP_TARGETS } = await import("../../help-targets");

    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-client-manual-1",
      frontend_target_contract_version: "2",
      locale: "en",
      topics: [
        {
          id: "tenant-admin.mailbox",
          title: "Central mailbox",
          summary: "Gmail guidance",
          module: "settings",
          route: "/admin/settings",
          order: 70,
          help_targets: [HELP_TARGETS.mailbox],
          safe_navigation: {
            route: "/admin/settings",
            settings_category: "mailbox",
          },
        },
      ],
    });
    vi.mocked(getHelpTopic).mockResolvedValue({
      id: "tenant-admin.mailbox",
      title: "Central mailbox",
      summary: "Gmail guidance",
      module: "settings",
      route: "/admin/settings",
      order: 70,
      help_targets: [HELP_TARGETS.mailbox],
      safe_navigation: {
        route: "/admin/settings",
        settings_category: "mailbox",
      },
      body: "# Gmail setup\n\nTutorial body.",
    });

    render(
      <>
        <input aria-label="Draft email" defaultValue="unsaved@example.com" />
        <ContextualHelpSheet />
      </>,
    );

    act(() => requestContextualHelp(HELP_TARGETS.mailbox));

    await waitFor(() => expect(screen.getByText("Tutorial body.")).toBeInTheDocument());
    expect(screen.getByLabelText("Draft email")).toHaveValue("unsaved@example.com");
    expect(getHelpTopic).toHaveBeenCalledWith("tenant-admin.mailbox");
  });
});
