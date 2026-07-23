import { beforeEach, describe, expect, it, vi } from "vitest";
import { useExportStore } from "../export-store";

// We must mock the API module before importing the store
vi.mock("@/features/admin/services/settings-api", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/admin/services/settings-api")
  >("@/features/admin/services/settings-api");
  return {
    ...actual,
    requestExport: vi.fn(),
    getExportStatus: vi.fn(),
    getExportDownloadUrl: vi.fn(),
  };
});

const api = await vi.mocked(
  import("@/features/admin/services/settings-api"),
);

const mockPending = {
  id: "job-1",
  status: "pending" as const,
  created_at: "2026-07-01T00:00:00Z",
  ready_at: null,
  expires_at: null,
  artifact_size_bytes: null,
  error_code: null,
  error_detail: null,
  attempt: 0,
  max_attempts: 3,
};

const mockReady = {
  id: "job-2",
  status: "ready" as const,
  created_at: "2026-07-01T00:00:00Z",
  ready_at: "2026-07-01T00:01:00Z",
  expires_at: "2026-07-04T00:01:00Z",
  artifact_size_bytes: 10240,
  error_code: null,
  error_detail: null,
  attempt: 1,
  max_attempts: 3,
};

describe("useExportStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset store to initial state
    useExportStore.getState().reset();
  });

  it("starts with empty state", () => {
    const state = useExportStore.getState();
    expect(state.job).toBeNull();
    expect(state.requesting).toBe(false);
    expect(state.statusLoading).toBe(false);
    expect(state.downloadLoading).toBe(false);
    expect(state.downloadUrl).toBeNull();
    expect(state.error).toBeNull();
  });

  it("refreshStatus sets job from API", async () => {
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(mockReady);

    await useExportStore.getState().refreshStatus();

    const state = useExportStore.getState();
    expect(state.job).toEqual(mockReady);
    expect(state.statusLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(api.getExportStatus).toHaveBeenCalledTimes(1);
  });

  it("refreshStatus handles null (no job)", async () => {
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(null);

    await useExportStore.getState().refreshStatus();

    const state = useExportStore.getState();
    expect(state.job).toBeNull();
    expect(state.statusLoading).toBe(false);
  });

  it("refreshStatus handles API error", async () => {
    const apiError = { response: { data: { detail: "Server error" } } };
    vi.mocked(api.getExportStatus).mockRejectedValueOnce(apiError);

    await useExportStore.getState().refreshStatus();

    const state = useExportStore.getState();
    expect(state.job).toBeNull();
    expect(state.error).toBe("Server error");
    expect(state.statusLoading).toBe(false);
  });

  it("requestExport creates a pending job", async () => {
    vi.mocked(api.requestExport).mockResolvedValueOnce(mockPending);

    await useExportStore.getState().requestExport();

    const state = useExportStore.getState();
    expect(state.job).toEqual(mockPending);
    expect(state.requesting).toBe(false);
    expect(state.error).toBeNull();
  });

  it("requestExport handles API error", async () => {
    const apiError = { response: { data: { detail: "Too many requests" } } };
    vi.mocked(api.requestExport).mockRejectedValueOnce(apiError);

    await useExportStore.getState().requestExport();

    const state = useExportStore.getState();
    expect(state.error).toBe("Too many requests");
    expect(state.requesting).toBe(false);
  });

  it("download returns URL for ready jobs", async () => {
    vi.mocked(api.getExportDownloadUrl).mockResolvedValueOnce({
      download_url: "https://r2.example.com/export.zip",
      expires_in: 900,
    });

    const url = await useExportStore.getState().download();

    expect(url).toBe("https://r2.example.com/export.zip");
    expect(useExportStore.getState().downloadUrl).toBe(url);
    expect(useExportStore.getState().downloadLoading).toBe(false);
  });

  it("download handles error", async () => {
    const apiError = { response: { data: { detail: "Not ready" } } };
    vi.mocked(api.getExportDownloadUrl).mockRejectedValueOnce(apiError);

    const url = await useExportStore.getState().download();

    expect(url).toBeNull();
    expect(useExportStore.getState().downloadUrl).toBeNull();
    expect(useExportStore.getState().error).toBe("Not ready");
  });

  it("starts polling for pending jobs", async () => {
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(mockPending);

    await useExportStore.getState().refreshStatus();

    expect(useExportStore.getState()._pollTimer).not.toBeNull();
  });

  it("stops polling when job becomes ready", async () => {
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(mockPending);
    await useExportStore.getState().refreshStatus();
    expect(useExportStore.getState()._pollTimer).not.toBeNull();

    // Transition to ready on next refresh
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(mockReady);
    await useExportStore.getState().refreshStatus();

    expect(useExportStore.getState()._pollTimer).toBeNull();
  });

  it("reset clears everything", async () => {
    vi.mocked(api.getExportStatus).mockResolvedValueOnce(mockReady);
    await useExportStore.getState().refreshStatus();
    expect(useExportStore.getState().job).not.toBeNull();

    useExportStore.getState().reset();
    const state = useExportStore.getState();
    expect(state.job).toBeNull();
    expect(state._pollTimer).toBeNull();
    expect(state.downloadUrl).toBeNull();
    expect(state.error).toBeNull();
  });
});
