import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/store/auth";
import { HelpCenterPage, SafeNavigationLink } from "../help-center-page";
import type { HelpTopic } from "../../services/help-api";
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
      content_version: "help-common-modules-1",
      frontend_target_contract_version: "2",
      locale: "en",
        topics: [
          {
            id: "tenant-admin.dashboard",
            title: "Business Dashboard",
            summary: "Dashboard overview",
            module: "dashboard",
            route: "/admin/dashboard",
            order: 10,
            help_targets: ["admin.dashboard"],
            safe_navigation: { route: "/admin/dashboard", settings_category: null },
          },
        ],
      });
    vi.mocked(getHelpTopic).mockResolvedValue({
      id: "tenant-admin.dashboard",
      title: "Business Dashboard",
      summary: "Dashboard overview",
      module: "dashboard",
      route: "/admin/dashboard",
      order: 10,
      help_targets: ["admin.dashboard"],
      safe_navigation: { route: "/admin/dashboard", settings_category: null },
      body: "# Business Dashboard\n\nDashboard content.",
    });
  });

  it("renders the authorized Client manual without Tenant Admin destinations", async () => {
    useAuthStore.setState({
      isAuthenticated: true,
      role: "client",
    });
    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-client-manual-1",
      frontend_target_contract_version: "2",
      locale: "en",
      topics: [
        {
          id: "client.dashboard",
          title: "Client Dashboard",
          summary: "Client overview",
          module: "dashboard",
          route: "/client/dashboard",
          order: 10,
          help_targets: ["client.dashboard"],
          safe_navigation: { route: "/client/dashboard", settings_category: null },
        },
      ],
    });
    vi.mocked(getHelpTopic).mockResolvedValue({
      id: "client.dashboard",
      title: "Client Dashboard",
      summary: "Client overview",
      module: "dashboard",
      route: "/client/dashboard",
      order: 10,
      help_targets: ["client.dashboard"],
      safe_navigation: { route: "/client/dashboard", settings_category: null },
      body: "# Client Dashboard\n\nClient-only content.",
    });

    render(<HelpCenterPage audience="client" />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Client Dashboard" })).toBeInTheDocument();
    });
    expect(screen.getByText("Client-only content.")).toBeInTheDocument();
    expect(screen.queryByText("Tenant Admin")).not.toBeInTheDocument();
  });

  it("renders topic navigation and the authenticated article", async () => {
    render(<HelpCenterPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Business Dashboard" })).toBeInTheDocument();
    });
    expect(screen.getAllByRole("button", { name: /Business Dashboard/ }).length).toBeGreaterThan(0);
    expect(screen.getByText("Dashboard content.")).toBeInTheDocument();
  });

  it("uses the wider Help layout and justified article copy", async () => {
    const { container } = render(<HelpCenterPage />);

    await waitFor(() => {
      expect(screen.getByText("Dashboard content.")).toBeInTheDocument();
    });

    expect(container.querySelector('[data-help-id="admin.help"]')).toHaveClass("max-w-screen-2xl");
    expect(screen.getByText("Dashboard content.")).toHaveClass("max-w-none", "text-justify");
  });

  it("scrolls to the article start after selecting a topic", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.mocked(getHelpIndex).mockResolvedValue({
      schema_version: 1,
      content_version: "help-common-modules-1",
      frontend_target_contract_version: "2",
      locale: "en",
      topics: [
        {
          id: "tenant-admin.dashboard",
          title: "Business Dashboard",
          summary: "Dashboard overview",
          module: "dashboard",
          route: "/admin/dashboard",
          order: 10,
          help_targets: ["admin.dashboard"],
          safe_navigation: { route: "/admin/dashboard", settings_category: null },
        },
        {
          id: "tenant-admin.mailbox",
          title: "Central mailbox",
          summary: "Mailbox overview",
          module: "settings",
          route: "/admin/settings",
          order: 20,
          help_targets: ["admin.settings.mailbox"],
          safe_navigation: { route: "/admin/settings", settings_category: "mailbox" },
        },
      ],
    });
    vi.mocked(getHelpTopic)
      .mockResolvedValueOnce({
        id: "tenant-admin.dashboard",
        title: "Business Dashboard",
        summary: "Dashboard overview",
        module: "dashboard",
        route: "/admin/dashboard",
        order: 10,
        help_targets: ["admin.dashboard"],
        safe_navigation: { route: "/admin/dashboard", settings_category: null },
        body: "# Business Dashboard\n\nDashboard content.",
      })
      .mockResolvedValueOnce({
        id: "tenant-admin.mailbox",
        title: "Central mailbox",
        summary: "Mailbox overview",
        module: "settings",
        route: "/admin/settings",
        order: 20,
        help_targets: ["admin.settings.mailbox"],
        safe_navigation: { route: "/admin/settings", settings_category: "mailbox" },
        body: "# Central mailbox\n\nMailbox content.",
      });

    render(<HelpCenterPage />);
    await waitFor(() => expect(screen.getByText("Dashboard content.")).toBeInTheDocument());
    scrollIntoView.mockClear();

    await userEvent.click(screen.getAllByRole("button", { name: /Central mailbox/ })[0]);

    await waitFor(() => expect(screen.getByText("Mailbox content.")).toBeInTheDocument());
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "start", behavior: "smooth" }),
    );
  });

  it("renders all safe module links for the first Pro Client guide", () => {
    const topic: HelpTopic = {
      id: "tenant-admin.first-pro-client",
      title: "Set up your first Pro Client",
      summary: "Follow the setup order.",
      module: "help",
      route: "/admin/catalog",
      order: 130,
      help_targets: [],
      safe_navigation: { route: "/admin/catalog", settings_category: null },
      safe_links: [
        { route: "/admin/clients", settings_category: null },
        { route: "/admin/subscriptions", settings_category: null },
      ],
      body: "Guide",
    };

    render(<SafeNavigationLink topic={topic} />);

    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/admin/catalog");
    expect(screen.getAllByRole("link")[1]).toHaveAttribute("href", "/admin/clients");
    expect(screen.getAllByRole("link")[2]).toHaveAttribute("href", "/admin/subscriptions");
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
          order: 10,
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
        content_version: "help-common-modules-1",
        frontend_target_contract_version: "2",
        locale: "en",
        topics: [
          {
            id: "tenant-admin.dashboard",
            title: "Business Dashboard",
            summary: "Dashboard overview",
            module: "dashboard",
            route: "/admin/dashboard",
            order: 10,
            help_targets: ["admin.dashboard"],
            safe_navigation: { route: "/admin/dashboard", settings_category: null },
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
