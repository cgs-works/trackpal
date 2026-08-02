import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ExecutorEnrollmentDialog } from "../executor-enrollment-dialog";
import {
  createLookupExecutor,
  enableLookupExecutor,
  testLookupExecutor,
  updateLookupExecutor,
  verifyLookupExecutor,
  type LookupExecutor,
} from "../../services/executor-api";

vi.mock("../../services/executor-api", () => ({
  createLookupExecutor: vi.fn(),
  enableLookupExecutor: vi.fn(),
  testLookupExecutor: vi.fn(),
  updateLookupExecutor: vi.fn(),
  verifyLookupExecutor: vi.fn(),
  mapExecutorError: vi.fn((_error: unknown, fallbackKey: string) => fallbackKey),
}));

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

const draft: LookupExecutor = {
  id: "executor-123",
  name: "Mail runner",
  provider_label: "Render",
  base_url: "",
  transport_mode: "https",
  lifecycle_status: "draft",
  health_status: "unknown",
  requires_reverification: false,
  max_concurrency: 2,
  secret_version: 1,
  pending_secret_version: null,
  has_hosting_password: false,
  last_verified_at: null,
  last_health_check_at: null,
  last_success_at: null,
  last_error_safe: null,
  active_jobs: 0,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
};

const mockedCreate = vi.mocked(createLookupExecutor);
const mockedUpdate = vi.mocked(updateLookupExecutor);
const mockedVerify = vi.mocked(verifyLookupExecutor);
const mockedTest = vi.mocked(testLookupExecutor);
const mockedEnable = vi.mocked(enableLookupExecutor);

beforeEach(() => {
  vi.clearAllMocks();
  mockedCreate.mockResolvedValue({ executor: draft, plain_secret: "plain-secret" });
  mockedUpdate.mockResolvedValue({ ...draft, base_url: "https://runner.example.test" });
  mockedVerify.mockResolvedValue({ ...draft, health_status: "healthy" });
  mockedTest.mockResolvedValue({
    status: "healthy",
    protocol_version: 2,
    runtime_version: "runner-1.4.0",
    max_concurrency: 4,
    executor: { ...draft, health_status: "healthy" },
  });
  mockedEnable.mockResolvedValue({ ...draft, lifecycle_status: "active" });
});

describe("ExecutorEnrollmentDialog", () => {
  it("requires identity fields before creating the draft", async () => {
    const user = userEvent.setup();
    render(<ExecutorEnrollmentDialog open onOpenChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "frontend.master.executors.next" }));

    expect(mockedCreate).not.toHaveBeenCalled();
    expect(screen.getByLabelText("frontend.master.executors.name")).toBeInvalid();
    expect(screen.getByLabelText("frontend.master.executors.provider")).toBeInvalid();
    expect(screen.getByLabelText("frontend.master.executors.max_concurrency")).toHaveAttribute("required");
  });

  it("creates a draft, shows one-time credentials, and clears the secret when dismissed", async () => {
    const user = userEvent.setup();
    render(<ExecutorEnrollmentDialog open onOpenChange={vi.fn()} />);

    await user.type(screen.getByLabelText("frontend.master.executors.name"), "Mail runner");
    await user.type(screen.getByLabelText("frontend.master.executors.provider"), "Render");
    await user.clear(screen.getByLabelText("frontend.master.executors.max_concurrency"));
    await user.type(screen.getByLabelText("frontend.master.executors.max_concurrency"), "2");
    await user.type(screen.getByLabelText("frontend.master.executors.hosting_email"), "host@example.com");
    await user.type(screen.getByLabelText("frontend.master.executors.hosting_password"), "host-password");
    await user.type(screen.getByLabelText("frontend.master.executors.dashboard_url"), "https://dashboard.example.test");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.next" }));

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledWith({
      name: "Mail runner",
      provider_label: "Render",
      max_concurrency: 2,
      hosting_account_email: "host@example.com",
      hosting_account_password: "host-password",
      dashboard_url: "https://dashboard.example.test",
    }));
    expect(screen.getByText("executor-123")).toBeInTheDocument();
    expect(screen.getByText("plain-secret")).toBeInTheDocument();

    const clipboardWriteText = vi.spyOn(navigator.clipboard, "writeText");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.copy_executor_id" }));
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.copy_secret" }));
    expect(clipboardWriteText).toHaveBeenNthCalledWith(1, "executor-123");
    expect(clipboardWriteText).toHaveBeenNthCalledWith(2, "plain-secret");
    expect(screen.getByText("frontend.master.executors.secret_copied")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.master.executors.credentials_continue" }));
    expect(screen.queryByText("plain-secret")).not.toBeInTheDocument();
    expect(screen.getByLabelText("frontend.master.executors.base_url")).toBeInTheDocument();
  });

  it("saves and verifies the connection, displays advertised capacity, then enables it", async () => {
    const user = userEvent.setup();
    render(<ExecutorEnrollmentDialog open onOpenChange={vi.fn()} />);

    await user.type(screen.getByLabelText("frontend.master.executors.name"), "Mail runner");
    await user.type(screen.getByLabelText("frontend.master.executors.provider"), "Render");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.next" }));
    await waitFor(() => expect(screen.getByText("plain-secret")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.credentials_continue" }));

    await user.type(screen.getByLabelText("frontend.master.executors.base_url"), "https://runner.example.test");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.verify" }));

    await waitFor(() => {
      expect(mockedUpdate).toHaveBeenCalledWith("executor-123", {
        base_url: "https://runner.example.test",
        transport_mode: "https",
        max_concurrency: 1,
      });
      expect(mockedVerify).toHaveBeenCalledWith("executor-123");
      expect(mockedTest).toHaveBeenCalledWith("executor-123");
    });
    expect(screen.getByText("runner-1.4.0")).toBeInTheDocument();
    expect(screen.getByText("frontend.master.executors.advertised_capacity_value")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.master.executors.enable" }));
    await waitFor(() => expect(mockedEnable).toHaveBeenCalledWith("executor-123"));
  });

  it("rejects configured capacity above the executor advertisement", async () => {
    const user = userEvent.setup();
    mockedTest.mockResolvedValueOnce({
      status: "healthy",
      protocol_version: 2,
      runtime_version: "runner-1.4.0",
      max_concurrency: 1,
      executor: { ...draft, health_status: "healthy" },
    });
    render(<ExecutorEnrollmentDialog open onOpenChange={vi.fn()} />);

    await user.type(screen.getByLabelText("frontend.master.executors.name"), "Mail runner");
    await user.type(screen.getByLabelText("frontend.master.executors.provider"), "Render");
    await user.clear(screen.getByLabelText("frontend.master.executors.max_concurrency"));
    await user.type(screen.getByLabelText("frontend.master.executors.max_concurrency"), "2");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.next" }));
    await waitFor(() => expect(screen.getByText("plain-secret")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.credentials_continue" }));
    await user.type(screen.getByLabelText("frontend.master.executors.base_url"), "https://runner.example.test");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.verify" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "frontend.master.executors.error_capacity_exceeds_advertised",
    );
    expect(screen.queryByRole("button", { name: "frontend.master.executors.enable" })).not.toBeInTheDocument();
    expect(mockedEnable).not.toHaveBeenCalled();
  });
});
