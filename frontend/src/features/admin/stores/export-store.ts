import { create } from "zustand";
import { t } from "@/i18n";
import {
  requestExport as apiRequestExport,
  getExportStatus as apiGetExportStatus,
  getExportDownloadUrl as apiGetExportDownloadUrl,
  cancelExport as apiCancelExport,
  type ExportJobStatusResponse,
  type ExportJobStatus,
} from "@/features/admin/services/settings-api";

interface ExportState {
  /** Current export job, or null if none. */
  job: ExportJobStatusResponse | null;
  /** The polling timer/interval id, so we can clear it. */
  _pollTimer: ReturnType<typeof setTimeout> | null;
  /** True while a request to create an export is in flight. */
  requesting: boolean;
  /** True while fetching status. */
  statusLoading: boolean;
  /** True while fetching the download URL. */
  downloadLoading: boolean;
  /** True while cancelling. */
  cancelling: boolean;
  /** Download URL once acquired, null initially or on error. */
  downloadUrl: string | null;
  /** User-facing error message, or null. */
  error: string | null;

  /** Fetch or refresh the current job status.  Returns new status or null. */
  refreshStatus: () => Promise<void>;
  /** Request a new export. */
  requestExport: () => Promise<void>;
  /** Cancel the current in-progress export. */
  cancelExport: () => Promise<void>;
  /** Get a fresh download URL and return it. */
  download: () => Promise<string | null>;
  /** Start polling when a job is pending/processing. */
  startPolling: () => void;
  /** Stop polling. */
  stopPolling: () => void;
  /** Reset to initial state. */
  reset: () => void;
}

const POLL_INTERVAL = 5000; // 5 seconds

function isPollable(status: ExportJobStatus): boolean {
  return status === "pending" || status === "processing";
}

function getExportError(error: any, fallbackKey: string): string {
  const detail = error?.response?.data?.detail;
  if (detail === "No ready export available") {
    return t("frontend.my_account.data_error_no_ready");
  }
  return detail || t(fallbackKey);
}

export const useExportStore = create<ExportState>((set, get) => ({
  job: null,
  _pollTimer: null,
  requesting: false,
  statusLoading: false,
  downloadLoading: false,
  cancelling: false,
  downloadUrl: null,
  error: null,

  refreshStatus: async () => {
    set({ statusLoading: true, error: null });
    try {
      const result = await apiGetExportStatus();
      if (result === null) {
        set({ job: null, statusLoading: false, downloadUrl: null });
        return;
      }
      set({ job: result, statusLoading: false, error: null });

      // Manage polling lifecycle
      if (isPollable(result.status)) {
        get().startPolling();
      } else {
        get().stopPolling();
      }
    } catch (err: any) {
      const msg = getExportError(err, "frontend.my_account.data_error_status");
      set({ error: msg, statusLoading: false });
    }
  },

  requestExport: async () => {
    set({ requesting: true, error: null, downloadUrl: null });
    try {
      const result = await apiRequestExport();
      set({ job: result, requesting: false, error: null });
      if (isPollable(result.status)) {
        get().startPolling();
      }
    } catch (err: any) {
      const msg = getExportError(err, "frontend.my_account.data_error_request");
      set({ error: msg, requesting: false });
    }
  },

  cancelExport: async () => {
    set({ cancelling: true, error: null });
    try {
      await apiCancelExport();
      // Refresh status to reflect cancellation
      await get().refreshStatus();
      set({ cancelling: false, error: null });
    } catch (err: any) {
      const msg = getExportError(err, "frontend.my_account.data_error_cancel");
      set({ error: msg, cancelling: false });
    }
  },

  download: async () => {
    set({ downloadLoading: true, error: null });
    try {
      const result = await apiGetExportDownloadUrl();
      set({ downloadUrl: result.download_url, downloadLoading: false });
      return result.download_url;
    } catch (err: any) {
      const msg = getExportError(err, "frontend.my_account.data_error_download");
      set({ error: msg, downloadLoading: false, downloadUrl: null });
      return null;
    }
  },

  startPolling: () => {
    const { _pollTimer } = get();
    if (_pollTimer !== null) return; // already polling

    const timer = setInterval(async () => {
      const currentState = get();
      if (!currentState.job) {
        currentState.stopPolling();
        return;
      }
      if (!isPollable(currentState.job.status)) {
        currentState.stopPolling();
        return;
      }
      await currentState.refreshStatus();
    }, POLL_INTERVAL);

    set({ _pollTimer: timer });
  },

  stopPolling: () => {
    const { _pollTimer } = get();
    if (_pollTimer !== null) {
      clearInterval(_pollTimer);
      set({ _pollTimer: null });
    }
  },

  reset: () => {
    get().stopPolling();
    set({
      job: null,
      _pollTimer: null,
      requesting: false,
      statusLoading: false,
      downloadLoading: false,
      cancelling: false,
      downloadUrl: null,
      error: null,
    });
  },
}));
