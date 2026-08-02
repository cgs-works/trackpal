import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LookupExecutorsPage } from "../lookup-executors-page";
import {
  deleteLookupExecutor,
  disableLookupExecutor,
  enableLookupExecutor,
  fetchLookupExecutors,
  revealLookupExecutorHostingPassword,
  rotateLookupExecutorSecret,
  testLookupExecutor,
  verifyLookupExecutor,
  type LookupExecutor,
} from "../../services/executor-api";

vi.mock("../../services/executor-api", () => ({
  deleteLookupExecutor: vi.fn(),
  disableLookupExecutor: vi.fn(),
  enableLookupExecutor: vi.fn(),
  fetchLookupExecutors: vi.fn(),
  mapExecutorError: vi.fn((_error: unknown, fallbackKey: string) => fallbackKey),
  revealLookupExecutorHostingPassword: vi.fn(),
  rotateLookupExecutorSecret: vi.fn(),
  testLookupExecutor: vi.fn(),
  verifyLookupExecutor: vi.fn(),
}));

vi.mock("@/i18n", () => ({
  getLocale: () => "en-US",
  t: (key: string) => key,
}));

const httpExecutor: LookupExecutor = {
  id: "http-executor",
  name: "HTTP executor",
  provider_label: "Render",
  base_url: "http://executor.example.test",
  transport_mode: "http_encrypted",
  lifecycle_status: "disabled",
  health_status: "unknown",
  requires_reverification: true,
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

const activeExecutor: LookupExecutor = {
  ...httpExecutor,
  id: "active-executor",
  name: "Active executor",
  provider_label: "Render",
  base_url: "https://executor.example.test",
  transport_mode: "https",
  lifecycle_status: "active",
  health_status: "healthy",
  requires_reverification: false,
  has_hosting_password: true,
  last_verified_at: "2026-08-01T12:00:00Z",
  active_jobs: 2,
};

const mockedFetch = vi.mocked(fetchLookupExecutors);
const mockedVerify = vi.mocked(verifyLookupExecutor);
const mockedReveal = vi.mocked(revealLookupExecutorHostingPassword);
const mockedRotate = vi.mocked(rotateLookupExecutorSecret);
const mockedEnable = vi.mocked(enableLookupExecutor);
const mockedDisable = vi.mocked(disableLookupExecutor);
const mockedTest = vi.mocked(testLookupExecutor);
const mockedDelete = vi.mocked(deleteLookupExecutor);

beforeEach(() => {
  vi.clearAllMocks();
  mockedFetch.mockResolvedValue([httpExecutor, activeExecutor]);
  mockedVerify.mockResolvedValue({ ...httpExecutor, health_status: "healthy" });
  mockedReveal.mockResolvedValue({ hosting_account_password: "hosting-password" });
  mockedRotate.mockResolvedValue({
    executor: { ...activeExecutor, secret_version: 2 },
    plain_secret: "rotated-secret",
  });
  mockedEnable.mockResolvedValue({ ...httpExecutor, lifecycle_status: "active" });
  mockedDisable.mockResolvedValue({ ...activeExecutor, lifecycle_status: "disabled" });
  mockedTest.mockResolvedValue({
    status: "healthy",
    protocol_version: 2,
    runtime_version: "runner-1.0.0",
    max_concurrency: 2,
    executor: activeExecutor,
  });
  mockedDelete.mockResolvedValue();
});

describe("executor security actions", () => {
  it("requires exact HTTP confirmation and the Master password before verifying", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("HTTP executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.verify" })[0]);
    await user.type(screen.getByLabelText("frontend.master.executors.http_confirmation"), "ALLOW");
    await user.type(screen.getByLabelText("frontend.master.executors.reveal_password"), "master-password");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.verify" }));

    expect(mockedVerify).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "frontend.master.executors.error_insecure_http_confirmation_required",
    );

    await user.clear(screen.getByLabelText("frontend.master.executors.http_confirmation"));
    await user.type(screen.getByLabelText("frontend.master.executors.http_confirmation"), "ALLOW HTTP");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.verify" }));

    await waitFor(() =>
      expect(mockedVerify).toHaveBeenCalledWith("http-executor", {
        confirmation: "ALLOW HTTP",
        password: "master-password",
      }),
    );
  });

  it("shows a verification error when the HTTPS verification request fails", async () => {
    const user = userEvent.setup();
    mockedFetch.mockResolvedValue([activeExecutor]);
    mockedVerify.mockRejectedValueOnce(new Error("network unavailable"));
    render(<LookupExecutorsPage />);
    await screen.findAllByText("Active executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.verify" })[0]);
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.verify" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "frontend.master.executors.error_verify",
    );
  });

  it("keeps the hosting password hidden until reveal and clears it on close", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("Active executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.reveal_hosting_password" })[0]);
    const masterPassword = screen.getByLabelText("frontend.master.executors.reveal_password");
    expect(masterPassword).toHaveAttribute("type", "password");
    await user.type(masterPassword, "master-password");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.reveal_hosting_password" }));

    const hostingPassword = await screen.findByLabelText("frontend.master.executors.revealed_password");
    expect(hostingPassword).toHaveValue("hosting-password");
    expect(hostingPassword).toHaveAttribute("type", "password");
    expect(screen.getByText("frontend.master.executors.reveal_warning")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.master.executors.show_password" }));
    expect(hostingPassword).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.cancel" }));
    expect(screen.queryByDisplayValue("hosting-password")).not.toBeInTheDocument();
  });

  it("shows a network error instead of an authentication error when revealing the hosting password fails", async () => {
    const user = userEvent.setup();
    mockedReveal.mockRejectedValueOnce(new Error("network unavailable"));
    render(<LookupExecutorsPage />);
    await screen.findAllByText("Active executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.reveal_hosting_password" })[0]);
    await user.type(screen.getByLabelText("frontend.master.executors.reveal_password"), "master-password");
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.reveal_hosting_password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "frontend.master.executors.error_reveal",
    );
  });

  it("shows a rotated secret once, closes confirmation, and refreshes lifecycle actions", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("Active executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.rotate_secret" })[0]);
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.confirm" }));
    expect(await screen.findByText("rotated-secret")).toBeInTheDocument();
    expect(screen.queryByText("frontend.master.executors.rotate_description")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.credentials_continue" }));
    expect(screen.queryByText("rotated-secret")).not.toBeInTheDocument();
  });

  it("enables an executor after confirmation and refreshes the list", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("HTTP executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.enable" })[0]);
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.confirm" }));

    await waitFor(() => expect(mockedEnable).toHaveBeenCalledWith("http-executor"));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(2));
  });

  it("deletes an executor after confirmation and refreshes the list", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("HTTP executor");

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.delete" })[0]);
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.confirm" }));

    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("http-executor"));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(2));
  });

  it("warns before a manual test, preserves active-job data after disable, and blocks busy deletion", async () => {
    const user = userEvent.setup();
    render(<LookupExecutorsPage />);
    await screen.findAllByText("Active executor");

    const deleteButtons = screen.getAllByRole("button", { name: "frontend.master.executors.delete" });
    expect(deleteButtons.some((button) => (button as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getAllByRole("button", { name: "frontend.master.executors.test" })[1]).toBeEnabled();

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.test" })[1]);
    expect(screen.getByText("frontend.master.executors.test_warning")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.confirm" }));
    await waitFor(() => expect(mockedTest).toHaveBeenCalledWith("active-executor"));

    await user.click(screen.getAllByRole("button", { name: "frontend.master.executors.disable" })[0]);
    await user.click(screen.getByRole("button", { name: "frontend.master.executors.confirm" }));
    await waitFor(() => expect(mockedDisable).toHaveBeenCalledWith("active-executor"));
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(3));
    expect(screen.getAllByText("2/2").length).toBeGreaterThan(0);
    expect(mockedDelete).not.toHaveBeenCalled();
  });
});
