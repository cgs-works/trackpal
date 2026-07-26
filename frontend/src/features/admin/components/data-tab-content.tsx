import { useEffect, useCallback, useState, useRef } from "react";
import {
  Database,
  Download,
  Loader2,
  FileArchive,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  User,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Separator } from "@/components/ui/separator";
import { t, getLocale } from "@/i18n";
import { useExportStore } from "../stores/export-store";
import { deleteAccount } from "../services/settings-api";


export function DataTabContent() {
  const {
    job,
    requesting,
    downloadLoading,
    cancelling,
    error,
    requestExport,
    refreshStatus,
    cancelExport: storeCancelExport,
    download,
    reset,
  } = useExportStore();

  const { isMasterSupportContext, dataSource } = useAuthStore();
  const isDemo = dataSource?.mode === "demo";

  const [downloading, setDownloading] = useState(false);
  const initialLoadDone = useRef(false);

  // ── Deletion state ──────────────────────────────────────────
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmWord, setDeleteConfirmWord] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const destructiveWord = getLocale() === "es" ? "ELIMINAR" : "DELETE";

  // Fetch current job status on mount
  useEffect(() => {
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      if (!isDemo) refreshStatus();
    }
    return () => {
      reset();
    };
  }, [isDemo, refreshStatus, reset]);

  const handleRequestExport = useCallback(async () => {
    await requestExport();
  }, [requestExport]);

  const handleCancelExport = useCallback(async () => {
    await storeCancelExport();
  }, [storeCancelExport]);

  const handleDownload = useCallback(async () => {
    const url = await download();
    if (url) {
      setDownloading(true);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.click();
      setTimeout(() => setDownloading(false), 2000);
    }
  }, [download]);

  // ── Deletion handlers ───────────────────────────────────────
  const handleDeleteClick = useCallback(() => {
    setDeletePassword("");
    setDeleteConfirmWord("");
    setDeleteError(null);
    setDeleteDialogOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deletePassword || !deleteConfirmWord) return;
    if (isDemo) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAccount({
        password: deletePassword,
        destructive_word: deleteConfirmWord,
      });
      // Success — redirect to login
      window.location.href = "/login?deleted=1";
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        t("frontend.my_account.danger_error");
      setDeleteError(msg);
    } finally {
      setDeleting(false);
    }
  }, [deletePassword, deleteConfirmWord, isDemo]);

  // ── Actor label ─────────────────────────────────────────────
  const actorLabel = () => {
    if (!job?.actor_role) return null;
    return job.actor_role === "master"
      ? t("frontend.my_account.data_actor_support")
      : t("frontend.my_account.data_actor_you");
  };

  // ── Cooldown info ───────────────────────────────────────────
  const cooldownInfo = () => {
    if (!job?.cooldown_until) return null;
    const cooldown = new Date(job.cooldown_until);
    const now = new Date();
    if (cooldown <= now) return null;
    const hours = Math.ceil((cooldown.getTime() - now.getTime()) / (1000 * 60 * 60));
    return t("frontend.my_account.data_cooldown", { hours: String(hours) });
  };

  // ── Expiry info ─────────────────────────────────────────────
  const expiryInfo = () => {
    if (!job?.expires_at) return null;
    const expires = new Date(job.expires_at);
    const now = new Date();
    if (expires <= now) return null;
    const hours = Math.ceil((expires.getTime() - now.getTime()) / (1000 * 60 * 60));
    return t("frontend.my_account.data_expires_in", { hours: String(hours) });
  };

  if (isDemo) {
    return (
      <div className="flex flex-col items-center gap-4 py-12 text-center">
        <div className="flex size-16 items-center justify-center rounded-full bg-muted">
          <Database className="size-8 text-muted-foreground" />
        </div>
        <div className="max-w-md space-y-2">
          <h3 className="text-lg font-semibold">{t("frontend.my_account.demo_data_title")}</h3>
          <p className="text-sm text-muted-foreground">{t("frontend.my_account.demo_data_description")}</p>
        </div>
        <div className="flex flex-wrap justify-center gap-3">
          <Button type="button" disabled variant="outline">{t("frontend.my_account.data_empty_action")}</Button>
          <Button type="button" disabled variant="destructive">{t("frontend.my_account.danger_delete_button")}</Button>
        </div>
      </div>
    );
  }

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

        <Separator className="my-6" />

        {isMasterSupportContext ? (
          /* Master Support Context — guide back to Dashboard */
          <div className="w-full max-w-md rounded-lg border p-4 text-center">
            <p className="text-sm text-muted-foreground">
              {t("frontend.master.delete_redirect_help")}
            </p>
          </div>
        ) : (
          /* Danger zone — Tenant Admin self-service deletion */
          <>
            <div className="w-full max-w-md rounded-lg border border-destructive/50 p-4">
              <h4 className="flex items-center gap-2 text-sm font-semibold text-destructive">
                <Trash2 className="size-4" />
                {t("frontend.my_account.danger_title")}
              </h4>
              <p className="mt-2 text-xs text-muted-foreground">
                {t("frontend.my_account.danger_description")}
              </p>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className="mt-3"
                onClick={handleDeleteClick}
              >
                {t("frontend.my_account.danger_delete_button")}
              </Button>
            </div>

            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    {t("frontend.my_account.danger_confirm_title")}
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {t("frontend.my_account.danger_confirm_description")}
                  </AlertDialogDescription>
                </AlertDialogHeader>

                <div className="grid gap-4 py-4">
                  <div className="grid gap-2">
                    <Label htmlFor="delete-password">
                      {t("frontend.my_account.danger_password_label")}
                    </Label>
                    <Input
                      id="delete-password"
                      type="password"
                      value={deletePassword}
                      onChange={(e) => setDeletePassword(e.target.value)}
                      disabled={deleting}
                      autoFocus
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="delete-confirm-word">
                      {t("frontend.my_account.danger_destructive_word_label", {
                        word: destructiveWord,
                      })}
                    </Label>
                    <Input
                      id="delete-confirm-word"
                      type="text"
                      value={deleteConfirmWord}
                      onChange={(e) => setDeleteConfirmWord(e.target.value)}
                      placeholder={destructiveWord}
                      disabled={deleting}
                    />
                  </div>
                  {deleteError && (
                    <p className="text-sm text-destructive">{deleteError}</p>
                  )}
                </div>

                <AlertDialogFooter>
                  <AlertDialogCancel disabled={deleting}>
                    {t("frontend.common.cancel")}
                  </AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDeleteConfirm}
                    disabled={
                      deleting ||
                      !deletePassword ||
                      deleteConfirmWord !== destructiveWord
                    }
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {deleting ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        {t("frontend.my_account.danger_deleting")}
                      </>
                    ) : (
                      t("frontend.my_account.danger_confirm_button")
                    )}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </>
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
        return <XCircle className="size-10 text-muted-foreground" />;
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

        {/* Actor attribution */}
        {actorLabel() && (
          <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
            <User className="size-3" />
            <span>{actorLabel()}</span>
          </div>
        )}

        {/* Artifact size */}
        {job.artifact_size_bytes != null && (
          <p className="text-xs text-muted-foreground">
            {formatBytes(job.artifact_size_bytes)}
          </p>
        )}

        {/* Expiry info */}
        {expiryInfo() && (
          <div className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
            <Clock className="size-3" />
            <span>{expiryInfo()}</span>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="flex flex-wrap justify-center gap-3">
        {/* Download current */}
        {job.status === "ready" && !job.replacement_job_id && (
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

        {/* Download ready but replacement in flight — download previous */}
        {job.status === "ready" && job.replacement_job_id && (
          <Button
            type="button"
            onClick={handleDownload}
            disabled={downloadLoading || downloading}
            variant="outline"
          >
            {downloadLoading || downloading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.data_downloading")}
              </>
            ) : (
              <>
                <Download className="mr-2 size-4" />
                {t("frontend.my_account.data_download_previous")}
              </>
            )}
          </Button>
        )}

        {/* Previous ready available for download during replacement */}
        {job.previous_ready && (job.status === "pending" || job.status === "processing") && (
          <Button
            type="button"
            onClick={handleDownload}
            disabled={downloadLoading || downloading}
            variant="outline"
          >
            {downloadLoading || downloading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.data_downloading")}
              </>
            ) : (
              <>
                <Download className="mr-2 size-4" />
                {t("frontend.my_account.data_download_previous")}
              </>
            )}
          </Button>
        )}

        {/* Cancel */}
        {(job.status === "pending" || job.status === "processing") && (
          <Button
            type="button"
            variant="secondary"
            onClick={handleCancelExport}
            disabled={cancelling}
          >
            {cancelling ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.data_cancelling")}
              </>
            ) : (
              <>
                <XCircle className="mr-2 size-4" />
                {t("frontend.my_account.data_cancel")}
              </>
            )}
          </Button>
        )}

        {/* Retry after failure or cancellation */}
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

      {/* Cooldown notice */}
      {cooldownInfo() && job.status === "ready" && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="size-3" />
          <span>{cooldownInfo()}</span>
        </div>
      )}

      {/* Processing indicator */}
      {(job.status === "pending" || job.status === "processing") && (
        <p className="text-xs text-muted-foreground">
          <FileArchive className="mr-1 inline size-3" />
          {t("frontend.my_account.data_status_processing")}
        </p>
      )}

      <Separator className="my-6" />

      {isMasterSupportContext ? (
        /* Master Support Context — guide back to Dashboard */
        <div className="w-full max-w-md rounded-lg border p-4 text-center">
          <p className="text-sm text-muted-foreground">
            {t("frontend.master.delete_redirect_help")}
          </p>
        </div>
      ) : (
        /* Danger zone — Tenant Admin self-service deletion */
        <>
          <div className="w-full max-w-md rounded-lg border border-destructive/50 p-4">
            <h4 className="flex items-center gap-2 text-sm font-semibold text-destructive">
              <Trash2 className="size-4" />
              {t("frontend.my_account.danger_title")}
            </h4>
            <p className="mt-2 text-xs text-muted-foreground">
              {t("frontend.my_account.danger_description")}
            </p>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              className="mt-3"
              onClick={handleDeleteClick}
            >
              {t("frontend.my_account.danger_delete_button")}
            </Button>
          </div>

          <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {t("frontend.my_account.danger_confirm_title")}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {t("frontend.my_account.danger_confirm_description")}
                </AlertDialogDescription>
              </AlertDialogHeader>

              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="delete-password">
                    {t("frontend.my_account.danger_password_label")}
                  </Label>
                  <Input
                    id="delete-password"
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    disabled={deleting}
                    autoFocus
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="delete-confirm-word">
                    {t("frontend.my_account.danger_destructive_word_label", {
                      word: destructiveWord,
                    })}
                  </Label>
                  <Input
                    id="delete-confirm-word"
                    type="text"
                    value={deleteConfirmWord}
                    onChange={(e) => setDeleteConfirmWord(e.target.value)}
                    placeholder={destructiveWord}
                    disabled={deleting}
                  />
                </div>
                {deleteError && (
                  <p className="text-sm text-destructive">{deleteError}</p>
                )}
              </div>

              <AlertDialogFooter>
                <AlertDialogCancel disabled={deleting}>
                  {t("frontend.common.cancel")}
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDeleteConfirm}
                  disabled={
                    deleting ||
                    !deletePassword ||
                    deleteConfirmWord !== destructiveWord
                  }
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleting ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      {t("frontend.my_account.danger_deleting")}
                    </>
                  ) : (
                    t("frontend.my_account.danger_confirm_button")
                  )}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
