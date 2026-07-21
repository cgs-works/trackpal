import { render, screen, waitFor } from "@testing-library/react";
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
});
