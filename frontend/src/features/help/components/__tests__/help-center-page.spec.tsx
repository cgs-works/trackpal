import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/store/auth";
import { HelpCenterPage } from "../help-center-page";
import { getHelpIndex, getHelpTopic, searchHelp } from "../../services/help-api";

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

  it("searches, selects a result, and clears the query", async () => {
    const user = userEvent.setup();
    vi.mocked(searchHelp).mockResolvedValue({
      query: "home",
      locale: "en",
      results: [
        {
          id: "tenant-admin.dashboard",
          title: "Business Dashboard",
          module: "dashboard",
          route: "/admin/dashboard",
          excerpt: "Dashboard overview",
        },
      ],
    });

    render(<HelpCenterPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Business Dashboard" })).toBeInTheDocument();
    });

    const searchInput = screen.getByRole("textbox", { name: "frontend.help.search" });
    await user.type(searchInput, "home");
    await waitFor(() => expect(searchHelp).toHaveBeenCalled());
    const resultButtons = screen.getAllByRole("button", { name: /Business Dashboard/ });
    expect(resultButtons).not.toHaveLength(0);

    await user.click(resultButtons[0]);
    await waitFor(() => expect(getHelpTopic).toHaveBeenCalledTimes(2));

    await user.click(screen.getByRole("button", { name: "frontend.help.clear_search" }));
    expect(searchInput).toHaveValue("");
    await waitFor(() => expect(getHelpTopic).toHaveBeenCalledTimes(3));
  });

  it("shows an empty state without retaining the previous article", async () => {
    vi.mocked(searchHelp).mockResolvedValue({
      query: "unknown",
      locale: "en",
      results: [],
    });

    render(<HelpCenterPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Business Dashboard" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByRole("textbox", { name: "frontend.help.search" }), {
      target: { value: "unknown" },
    });
    await waitFor(() => {
      expect(screen.getAllByText("frontend.help.no_results")[0]).toBeInTheDocument();
    });
    expect(screen.queryByText("Dashboard content.")).not.toBeInTheDocument();
  });

  it("offers retry when the Help index fails", async () => {
    const user = userEvent.setup();
    vi.mocked(getHelpIndex)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
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

    render(<HelpCenterPage />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "frontend.help.retry" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "frontend.help.retry" }));
    await waitFor(() => {
      expect(screen.getByText("Dashboard content.")).toBeInTheDocument();
    });
  });

  it("does not fetch or expose Help while the release gate is disabled", () => {
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "false");

    render(<HelpCenterPage />);

    expect(screen.getByTestId("help-disabled")).toBeInTheDocument();
    expect(getHelpIndex).not.toHaveBeenCalled();
  });
});
