import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ClientConsoleExperience } from "../client-console-experience";
import { createDemoBaseline } from "../../services/demo-baseline";
import { createDemoWorkspaceRepository } from "../../services/demo-workspace";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore, type DemoAuthMetadata } from "@/store/auth";
import api from "@/lib/api";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key} ${Object.values(params).join(" ")}` : key,
}));

vi.mock("@/lib/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const matchMedia = vi.fn();

const metadata: DemoAuthMetadata = {
  tenantId: "client-console-demo",
  name: "Client Console Demo",
  plan: "pro",
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
    tenantPlan: "pro",
    demo: metadata,
    dataSource: createDataSource(
      { tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata },
      repository,
    ),
    isAuthenticated: true,
    role: "tenant",
    isMasterSupportContext: false,
  });
}

describe("ClientConsoleExperience", () => {
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

  it("reads current local clients and active subscriptions without HTTP traffic", async () => {
    render(<ClientConsoleExperience onBack={vi.fn()} onCancel={vi.fn()} />);

    const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
    expect(screen.getByText(/frontend\.demo_simulator\.client_select/)).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));

    expect(await screen.findByText(/frontend\.demo_simulator\.client_subscriptions/)).toBeInTheDocument();
    expect(screen.getByText(/Netflix/)).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("uses enabled local services and allows reduced-motion cancellation", async () => {
    matchMedia.mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    const onCancel = vi.fn();
    render(<ClientConsoleExperience onBack={vi.fn()} onCancel={onCancel} />);
    const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");

    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    expect(await screen.findByText("frontend.demo_simulator.client_access_code_title")).toBeInTheDocument();

    const codeInput = screen.getByLabelText("frontend.demo_simulator.message_input_label");
    fireEvent.change(codeInput, { target: { value: "codigo" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.service_input_label"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.email_input_label"), { target: { value: "member@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(api.get).not.toHaveBeenCalled();
    matchMedia.mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
  });

  it("handles the inactive empty state and exits on universal cancel", async () => {
    const onCancel = vi.fn();
    render(<ClientConsoleExperience onBack={vi.fn()} onCancel={onCancel} />);
    const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");

    fireEvent.change(input, { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));

    expect(await screen.findByText("frontend.demo_simulator.client_subscriptions_inactive")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("frontend.demo_simulator.message_input_label"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
