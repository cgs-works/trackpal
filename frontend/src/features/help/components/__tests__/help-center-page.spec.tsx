import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/store/auth";
import { HelpCenterPage } from "../help-center-page";
import { getHelpIndex, getHelpTopic } from "../../services/help-api";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: { to: string; children: ReactNode }) => (
    <a href={to} {...props}>{children}</a>
  ),
  Navigate: () => null,
}));

vi.mock("../../services/help-api", () => ({
  getHelpIndex: vi.fn(),
  getHelpTopic: vi.fn(),
  searchHelp: vi.fn(),
}));

describe("HelpCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "true");
    useAuthStore.setState({
      isAuthenticated: true,
      role: "tenant",
    });
    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-tracer-1",
      frontend_target_contract_version: "1",
      locale: "en",
      topics: [
        {
          id: "tenant-admin.dashboard",
          title: "Business Dashboard",
          summary: "Dashboard overview",
          module: "dashboard",
          route: "/admin/dashboard",
        },
      ],
    });
    vi.mocked(getHelpTopic).mockResolvedValue({
      id: "tenant-admin.dashboard",
      title: "Business Dashboard",
      summary: "Dashboard overview",
      module: "dashboard",
      route: "/admin/dashboard",
      body: "# Business Dashboard\n\nDashboard content.",
    });
  });

  it("renders topic navigation and the authenticated article", async () => {
    render(<HelpCenterPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Business Dashboard" })).toBeInTheDocument();
    });
    expect(screen.getAllByRole("button", { name: /Business Dashboard/ }).length).toBeGreaterThan(0);
    expect(screen.getByText("Dashboard content.")).toBeInTheDocument();
  });

  it("does not fetch or expose Help while the release gate is disabled", () => {
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");

    render(<HelpCenterPage />);

    expect(screen.getByTestId("help-disabled")).toBeInTheDocument();
    expect(getHelpIndex).not.toHaveBeenCalled();
  });
});
