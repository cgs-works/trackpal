import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("runs Tenant Admin client mutations through the local repository", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await waitFor(() => expect(screen.getByText(/frontend\.demo_simulator\.tenant_menu/)).toBeInTheDocument());
    await send("1");
    expect(await screen.findByText(/frontend\.demo_simulator\.clients_title/)).toBeInTheDocument();
    await send("1");
    expect(await screen.findByText(/Avery Stone/)).toBeInTheDocument();
    await send("1");
    await send("2");
    expect(await screen.findByText(/frontend\.demo_simulator\.client_deactivate_confirm/)).toBeInTheDocument();
    await send("CONFIRM");
    await waitFor(() => expect(screen.getByText(/frontend\.demo_simulator\.client_deactivated/)).toBeInTheDocument());

    await waitFor(() => {
      const state = useAuthStore.getState().dataSource.workspace?.read();
      const client = state && (state.plan_specific.clients as Array<{ full_name: string; is_active: boolean }>).find((item) => item.full_name === "Avery Stone");
      expect(client?.is_active).toBe(false);
    });
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("runs Tenant Admin subscription listing, reveal, filters, and lifecycle locally", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await send("4");
    expect(await screen.findByText("frontend.demo_simulator.subscriptions_title")).toBeInTheDocument();
    await send("1");
    expect(await screen.findByText(/demo\.expiring\.1@example\.test/)).toBeInTheDocument();
    await send("2");
    await send("2");
    expect(await screen.findByText(/demo-expiring-1-secret/)).toBeInTheDocument();
    await send("3");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_cancel_confirm/)).toBeInTheDocument();
    await send("not-confirmed");
    expect(await screen.findByText("frontend.demo_simulator.confirm_reprompt")).toBeInTheDocument();
    await send("CONFIRM");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_cancelled/)).toBeInTheDocument();

    const state = useAuthStore.getState().dataSource.workspace?.read();
    const subscriptions = state?.plan_specific.subscriptions as Array<{ streaming_email: string; status: string }> | undefined;
    expect(subscriptions?.find((subscription) => subscription.streaming_email === "demo.expiring.1@example.test")?.status).toBe("cancelled");

    await send("9");
    await send("9");
    await send("2");
    await send("3");
    expect((await screen.findAllByText(/demo\.expired@example\.test/)).length).toBeGreaterThan(0);
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("edits, renews, cancels, and reactivates a local subscription", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await send("4");
    await send("1");
    await send("1");
    await send("1");
    await send("1");
    await send("edited.local@example.test");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_updated/)).toBeInTheDocument();
    await send("4");
    await send("1");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_renewed/)).toBeInTheDocument();
    await send("3");
    await send("CONFIRM");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_cancelled/)).toBeInTheDocument();
    await send("3");
    await send("1");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_reactivated/)).toBeInTheDocument();

    const subscriptions = useAuthStore.getState().dataSource.workspace?.read()?.plan_specific.subscriptions as Array<{ streaming_email: string; status: string }>;
    expect(subscriptions.some((subscription) => subscription.streaming_email === "edited.local@example.test" && subscription.status === "active")).toBe(true);
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("creates a subscription only after the final confirmation and keeps invalid input local", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await send("4");
    await send("3");
    await send("1");
    await send("1");
    await send("1");
    await send("new.local@example.test");
    await send("-");
    await send("-");
    await send("-");
    await send("1");
    await send("2026-07-25");
    await send("not-confirmed");
    expect(await screen.findByText("frontend.demo_simulator.confirm_reprompt")).toBeInTheDocument();

    const before = useAuthStore.getState().dataSource.workspace?.read();
    expect(before?.plan_specific.subscriptions).toHaveLength(8);
    await send("CONFIRM");
    expect(await screen.findByText(/frontend\.demo_simulator\.subscription_created/)).toBeInTheDocument();
    const after = useAuthStore.getState().dataSource.workspace?.read();
    expect(after?.plan_specific.subscriptions).toHaveLength(9);
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("creates catalog services locally and keeps invalid confirmations non-mutating", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await waitFor(() => expect(screen.getByText(/frontend\.demo_simulator\.tenant_menu/)).toBeInTheDocument());
    await send("2");
    expect(await screen.findByText(/frontend\.demo_simulator\.catalog_title/)).toBeInTheDocument();
    await send("2");
    await send("New Local Service");

    await waitFor(() => {
      const state = useAuthStore.getState().dataSource.workspace?.read();
      const services = state?.plan_specific.services as Array<{ name: string }> | undefined;
      expect(services?.some((service) => service.name === "New Local Service")).toBe(true);
    });
    expect(screen.getAllByText(/New Local Service/).length).toBeGreaterThan(0);
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("supports 8 pagination, 9 back, and 0 cancellation in Tenant Admin flows", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await send("1");
    await send("1");
    await send("8");
    expect(await screen.findByText(/Jon Bell/)).toBeInTheDocument();
    await send("9");
    expect(screen.getAllByText(/Avery Stone/).length).toBeGreaterThan(0);
    await send("0");
    expect(screen.getAllByText(/frontend\.demo_simulator\.mode_request/).length).toBeGreaterThan(0);
  });

  it("previews catalog relations before delete and does not mutate on a bad confirmation", async () => {
    authenticateProDemo();
    render(<DemoWhatsappSimulator />);
    fireEvent.click(screen.getByRole("tab", { name: "frontend.demo_simulator.mode_operation" }));

    const send = async (value: string) => {
      const input = await screen.findByLabelText("frontend.demo_simulator.message_input_label");
      await act(async () => {
        fireEvent.change(input, { target: { value } });
        fireEvent.click(screen.getByRole("button", { name: "frontend.demo_simulator.send" }));
      });
    };

    await send("1");
    await send("2");
    await send("1");
    await send("1");
    await send("4");
    await send("1");
    expect(await screen.findByText(/frontend\.demo_simulator\.catalog_delete_confirm/)).toBeInTheDocument();
    await send("not-confirmed");
    expect(await screen.findByText(/frontend\.demo_simulator\.catalog_confirm_reprompt/)).toBeInTheDocument();
    const state = useAuthStore.getState().dataSource.workspace?.read();
    const services = state?.plan_specific.services as Array<{ name: string }> | undefined;
    expect(services).toHaveLength(3);
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
