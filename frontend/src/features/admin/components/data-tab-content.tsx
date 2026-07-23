import { useEffect, useCallback, useState, useRef } from "react";
import { Database, Download, Loader2, FileArchive, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { useExportStore } from "../stores/export-store";

export function DataTabContent() {
  const {
    job,
    requesting,
    statusLoading,
    downloadLoading,
    downloadUrl,
    error,
    requestExport,
    refreshStatus,
    download,
    reset,
  } = useExportStore();

  const [downloading, setDownloading] = useState(false);
  const initialLoadDone = useRef(false);

  // Fetch current job status on mount
  useEffect(() => {
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      refreshStatus();
    }
    return () => {
      reset();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRequestExport = useCallback(async () => {
    await requestExport();
  }, [requestExport]);

  const handleDownload = useCallback(async () => {
    const url = await download();
    if (url) {
      setDownloading(true);
      // Open in new tab (or trigger download via anchor)
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.click();
      // Reset downloading state after a short delay
      setTimeout(() => setDownloading(false), 2000);
    }
  }, [download]);

  // ── No job exists (empty state) ─────────────────────────────
  if (!job) {
    return (
      <div className="flex flex-col items-center gap-4 py-12 text-center">
        <div className="flex size-16 items-center justify-center rounded-full bg-muted">
          <Database className="size-8 text-muted-foreground" />
        </div>
        <div className="max-w-md space-y-2">
          <h3 className="text-lg font-semibold">
            {t("frontend.my_account.data_empty_title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("frontend.my_account.data_empty_description")}
          </p>
        </div>
        <Button
          type="button"
          onClick={handleRequestExport}
          disabled={requesting}
        >
          {requesting ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              {t("frontend.my_account.data_requesting")}
            </>
          ) : (
            t("frontend.my_account.data_empty_action")
          )}
        </Button>
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
      </div>
    );
  }

  // ── Job exists ──────────────────────────────────────────────
  const statusIcon = () => {
    switch (job.status) {
      case "pending":
        return <Loader2 className="size-10 animate-spin text-muted-foreground" />;
      case "processing":
        return <Loader2 className="size-10 animate-spin text-primary" />;
      case "ready":
        return <CheckCircle2 className="size-10 text-green-600" />;
      case "failed":
        return <AlertCircle className="size-10 text-destructive" />;
      case "cancelled":
        return <AlertCircle className="size-10 text-muted-foreground" />;
    }
  };

  const statusLabel = () => {
    switch (job.status) {
      case "pending":
        return t("frontend.my_account.data_status_pending");
      case "processing":
        return t("frontend.my_account.data_status_processing");
      case "ready":
        return t("frontend.my_account.data_status_ready");
      case "failed":
        return t("frontend.my_account.data_status_failed");
      case "cancelled":
        return t("frontend.my_account.data_status_cancelled");
    }
  };

  return (
    <div className="flex flex-col items-center gap-4 py-12 text-center">
      <div className="flex size-16 items-center justify-center rounded-full bg-muted">
        {statusIcon()}
      </div>
      <div className="max-w-md space-y-2">
        <h3 className="text-lg font-semibold">
          {t("frontend.my_account.data_heading")}
        </h3>
        <p className="text-sm text-muted-foreground">
          {t("frontend.my_account.data_description")}
        </p>
        <div className="pt-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium">
            <span
              className={`size-2 rounded-full ${
                job.status === "ready"
                  ? "bg-green-500"
                  : job.status === "failed" || job.status === "cancelled"
                    ? "bg-destructive"
                    : "bg-amber-500"
              }`}
            />
            {statusLabel()}
          </span>
        </div>
        {job.artifact_size_bytes != null && (
          <p className="text-xs text-muted-foreground">
            {formatBytes(job.artifact_size_bytes)}
          </p>
        )}
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="flex gap-3">
        {job.status === "ready" && (
          <Button
            type="button"
            onClick={handleDownload}
            disabled={downloadLoading || downloading}
          >
            {downloadLoading || downloading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.data_downloading")}
              </>
            ) : (
              <>
                <Download className="mr-2 size-4" />
                {t("frontend.my_account.data_download")}
              </>
            )}
          </Button>
        )}

        {job.status === "failed" || job.status === "cancelled" ? (
          <Button
            type="button"
            variant="outline"
            onClick={handleRequestExport}
            disabled={requesting}
          >
            {requesting ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.data_requesting")}
              </>
            ) : (
              t("frontend.my_account.data_request_export")
            )}
          </Button>
        ) : null}
      </div>

      {(job.status === "pending" || job.status === "processing") && (
        <p className="text-xs text-muted-foreground">
          <FileArchive className="mr-1 inline size-3" />
          {t("frontend.my_account.data_status_processing")}
        </p>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
