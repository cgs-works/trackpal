import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DemoWhatsappSimulator } from "../demo-whatsapp-simulator";
import { createDemoBaseline } from "../../services/demo-baseline";
import { createDemoWorkspaceRepository } from "../../services/demo-workspace";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore, type DemoAuthMetadata } from "@/store/auth";
import api from "@/lib/api";

const matchMedia = vi.fn();

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key} ${Object.values(params).join(" ")}` : key,
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

vi.mock("@/lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const metadata: DemoAuthMetadata = {
  tenantId: "starter-simulator",
  name: "Simulator Demo",
  plan: "starter",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

function authenticateDemo() {
  const repository = createDemoWorkspaceRepository(metadata.tenantId);
  repository.reset(metadata, createDemoBaseline);
  useAuthStore.setState({
    token: "demo-token",
    user: { id: "demo-user", username: "demo-admin", role: "tenant" },
    activeTenantId: metadata.tenantId,
    tenantPlan: "starter",
    demo: metadata,
    dataSource: createDataSource(
      { tenantId: metadata.tenantId, tenantPlan: "starter", demo: metadata },
      repository,
    ),
    isAuthenticated: true,
    role: "tenant",
    isMasterSupportContext: false,
  });
}

function authenticateProDemo() {
  const proMetadata = { ...metadata, tenantId: "pro-simulator", plan: "pro" as const };
  const repository = createDemoWorkspaceRepository(proMetadata.tenantId);
  repository.reset(proMetadata, createDemoBaseline);
  useAuthStore.setState({
    token: "demo-token",
    user: { id: "demo-user", username: "demo-admin", role: "tenant" },
    activeTenantId: proMetadata.tenantId,
    tenantPlan: "pro",
    demo: proMetadata,
    dataSource: createDataSource(
      { tenantId: proMetadata.tenantId, tenantPlan: "pro", demo: proMetadata },
      repository,
    ),
    isAuthenticated: true,
    role: "tenant",
    isMasterSupportContext: false,
  });
}

describe("DemoWhatsappSimulator", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    matchMedia.mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    Object.defineProperty(window, "matchMedia", { configurable: true, value: matchMedia });
    authenticateDemo();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("rejects production access but exposes the Pro simulator modes", async () => {
    useAuthStore.setState({
      dataSource: createDataSource({ tenantId: "production", tenantPlan: "starter", demo: null }),
      demo: null,
      tenantPlan: "starter",
    });

    const { unmount } = render(<DemoWhatsappSimulator />);
    expect(screen.getByText("404")).toBeInTheDocument();
    unmount();

    authenticateDemo();
    useAuthStore.setState({
      tenantPlan: "pro",
      demo: { ...metadata, plan: "pro" },
      dataSource: createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: { ...metadata, plan: "pro" } }),
    });
    render(<DemoWhatsappSimulator />);
    expect(await screen.findByRole("tab", { name: "frontend.demo_simulator.mode_request" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" })).toBeInTheDocument();
  });

  it("renders Pro Request and Operation modes with the documented console roots", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);

    expect(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_request" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));
    expect(await screen.findByText(/frontend\.demo_simulator\.role_prompt/)).toBeInTheDocument();
    expect(screen.getByText(/frontend\.demo_simulator\.role_tenant_admin/)).toBeInTheDocument();
    expect(screen.getByText(/frontend\.demo_simulator\.role_client/)).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("renders only the Starter Request experience from local services", async () => {
    render(<DemoWhatsappSimulator />);

    expect(await screen.findByText("frontend.demo_simulator.welcome")).toBeInTheDocument();
    expect(screen.getByText("frontend.demo_simulator.no_operation_notice")).toBeInTheDocument();
    expect(screen.getByText("Secure Mail")).toBeInTheDocument();
    expect(screen.getByText("Account Access")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("accepts a code request, validates email accessibly, and delivers a six-digit code", async () => {
    render(<DemoWhatsappSimulator />);
    const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");

    fireEvent.change(input, { target: { value: "código" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    expect(await screen.findByText(/frontend\.demo_simulator\.service_prompt/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.service_input_label"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));

    const email = screen.getByLabelText("frontend.demo_simulator.email_input_label");
    fireEvent.change(email, { target: { value: "invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    expect(screen.getAllByText("frontend.demo_simulator.invalid_email").some((element) => element.getAttribute("role") === "alert")).toBe(true);
    expect(email).toHaveAttribute("aria-invalid", "true");

    fireEvent.change(email, { target: { value: "member@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    expect(await screen.findByRole("status")).toHaveTextContent("frontend.demo_simulator.searching");

    await waitFor(() => {
      expect(screen.getByText(/frontend\.demo_simulator\.code_found/)).toBeInTheDocument();
    }, { timeout: 1500 });
    expect(screen.getByText(/\d{6}/)).toBeInTheDocument();
  });

  it("cancels processing timers on unmount and supports reduced motion", async () => {
    matchMedia.mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    const { unmount } = render(<DemoWhatsappSimulator />);
    const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");

    fireEvent.change(input, { target: { value: "code" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.service_input_label"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.email_input_label"), {
      target: { value: "member@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));

    unmount();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByTestId("demo-whatsapp-simulator")).not.toBeInTheDocument();
  });

  it("reset conversation clears chat without changing workspace services", async () => {
    render(<DemoWhatsappSimulator />);
    expect(await screen.findByText("Secure Mail")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.reset" }));

    expect(screen.getByText("frontend.demo_simulator.welcome")).toBeInTheDocument();
    expect(screen.queryByText(/frontend\.demo_simulator\.service_prompt/)).not.toBeInTheDocument();
    expect(screen.getByText("Secure Mail")).toBeInTheDocument();
  });
});
