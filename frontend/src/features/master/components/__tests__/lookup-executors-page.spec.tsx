import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LookupExecutorsPage } from "../lookup-executors-page";
import {
  fetchLookupExecutors,
  type LookupExecutor,
} from "../../services/executor-api";

vi.mock("../../services/executor-api", () => ({
  fetchLookupExecutors: vi.fn(),
  mapExecutorError: vi.fn((_error: unknown, fallbackKey: string) => fallbackKey),
}));

const executors: LookupExecutor[] = [
  {
    id: "draft-id",
    name: "Draft executor",
    provider_label: "Render",
    base_url: "https://draft.example.test",
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
    created_at: "2026-07-31T12:00:00Z",
    updated_at: "2026-07-31T12:00:00Z",
  },
  {
    id: "active-id",
    name: "Healthy executor",
    provider_label: "Fly",
    base_url: "https://healthy.example.test",
    transport_mode: "https",
    lifecycle_status: "active",
    health_status: "healthy",
    requires_reverification: false,
    max_concurrency: 4,
    secret_version: 2,
    pending_secret_version: null,
    has_hosting_password: true,
    last_verified_at: "2026-07-31T12:00:00Z",
    last_health_check_at: "2026-07-31T12:30:00Z",
    last_success_at: "2026-07-31T12:31:00Z",
    last_error_safe: null,
    active_jobs: 2,
    created_at: "2026-07-30T12:00:00Z",
    updated_at: "2026-07-31T12:00:00Z",
  },
  {
    id: "quarantined-id",
    name: "HTTP executor",
    provider_label: "Custom",
    base_url: "http://legacy.example.test",
    transport_mode: "http_encrypted",
    lifecycle_status: "disabled",
    health_status: "unhealthy",
    requires_reverification: true,
    max_concurrency: 1,
    secret_version: 1,
    pending_secret_version: 2,
    has_hosting_password: false,
    last_verified_at: null,
    last_health_check_at: "2026-07-31T12:30:00Z",
    last_success_at: null,
    last_error_safe: "Connection refused by upstream",
    active_jobs: 1,
    created_at: "2026-07-29T12:00:00Z",
    updated_at: "2026-07-31T12:00:00Z",
  },
];

const mockedFetchLookupExecutors = vi.mocked(fetchLookupExecutors);

beforeEach(() => {
  vi.clearAllMocks();
  mockedFetchLookupExecutors.mockResolvedValue(executors);
});

describe("LookupExecutorsPage", () => {
  it("renders loading, then reports load errors and retries", async () => {
    let resolveRequest!: (value: LookupExecutor[]) => void;
    const pending = new Promise<LookupExecutor[]>((resolve) => {
      resolveRequest = resolve;
    });
    mockedFetchLookupExecutors.mockReturnValueOnce(pending);

    render(<LookupExecutorsPage />);
    expect(screen.getByText("frontend.master.executors.loading")).toBeInTheDocument();

    resolveRequest(executors);
    await waitFor(() => expect(screen.getAllByText("Draft executor")[0]).toBeInTheDocument());

    mockedFetchLookupExecutors.mockRejectedValueOnce(new Error("network"));
    await userEvent.click(
      screen.getByRole("button", { name: "frontend.master.executors.refresh" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "frontend.master.executors.error_load",
    );

    mockedFetchLookupExecutors.mockResolvedValueOnce(executors);
    await userEvent.click(
      screen.getByRole("button", { name: "frontend.master.executors.retry" }),
    );
    await waitFor(() => expect(screen.getAllByText("Healthy executor")[0]).toBeInTheDocument());
    expect(mockedFetchLookupExecutors).toHaveBeenCalledTimes(3);
  });

  it("renders the empty operational state", async () => {
    mockedFetchLookupExecutors.mockResolvedValueOnce([]);

    render(<LookupExecutorsPage />);

    expect(await screen.findByText("frontend.master.executors.empty")).toBeInTheDocument();
    expect(screen.queryByTestId("executor-desktop-table")).not.toBeInTheDocument();
  });

  it("renders desktop table and mobile cards with operational metadata", async () => {
    render(<LookupExecutorsPage />);

    await waitFor(() => expect(screen.getAllByText("Healthy executor")[0]).toBeInTheDocument());

    expect(screen.getByTestId("executor-desktop-table")).toHaveClass("hidden", "md:block");
    expect(screen.getByTestId("executor-mobile-list")).toHaveClass("md:hidden");
    expect(screen.getAllByText("frontend.master.executors.status_draft").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.executors.status_active").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.executors.status_disabled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.executors.status_healthy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.executors.status_unhealthy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("HTTPS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("HTTP encrypted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.executors.reverification_required").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2/4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Connection refused by upstream").length).toBeGreaterThan(0);
  });

  it("loads once until manual refresh and never renders secrets", async () => {
    render(<LookupExecutorsPage />);

    await waitFor(() => expect(screen.getAllByText("Healthy executor")[0]).toBeInTheDocument());
    expect(mockedFetchLookupExecutors).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("plain-secret")).not.toBeInTheDocument();
    expect(screen.queryByText("hosting-password")).not.toBeInTheDocument();
    expect(screen.queryByText("secret_encrypted")).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "frontend.master.executors.refresh" }),
    );
    await waitFor(() => expect(mockedFetchLookupExecutors).toHaveBeenCalledTimes(2));
  });
});
