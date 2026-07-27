import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { DemoCountdown } from "@/features/demo/components/demo-countdown";
import { createDemoBaseline } from "@/features/demo/services/demo-baseline";

export function DemoBanner({
  showConnectivityWarning = false,
}: {
  showConnectivityWarning?: boolean;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [resetError, setResetError] = useState(false);
  const demo = useAuthStore((s) => s.demo);
  const dataSource = useAuthStore((s) => s.dataSource);
  const workspace = dataSource.workspace;
  const [recoveryNotice] = useState(() => workspace?.consumeRecoveryNotice?.() ?? null);

  if (!demo || demo.status !== "active") return null;
  const activeDemo = demo;
  const storageState = workspace?.storageState?.() ?? "unavailable";
  const resetDisabled = storageState !== "available";

  function handleReset() {
    if (!workspace) return;
    if (workspace.storageState() !== "available") {
      setResetError(true);
      return;
    }
    try {
      workspace.reset(activeDemo, createDemoBaseline);
      setResetError(false);
      setConfirmOpen(false);
      window.location.reload();
    } catch {
      setResetError(true);
    }
  }

  const planLabel =
    demo.plan === "pro"
      ? t("frontend.master.demos.pro")
      : t("frontend.master.demos.starter");

  return (
    <Alert className="m-4 mb-0" data-testid="demo-banner">
      <AlertTitle className="flex flex-wrap items-center gap-2">
        {t("frontend.demo.banner.title")}{" "}
        <span className="text-xs font-normal text-muted-foreground">
          ({planLabel})
        </span>
      </AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        {recoveryNotice && (
          <p role="status" data-testid="demo-workspace-recovered" className="font-medium">
            {t("frontend.demo.banner.workspace_recovered")}
          </p>
        )}
        {storageState === "unavailable" && (
          <p role="alert" data-testid="demo-storage-unavailable" className="font-medium text-destructive">
            {t("frontend.demo.banner.storage_unavailable")}
          </p>
        )}
        {storageState === "quota_exceeded" && (
          <p role="alert" data-testid="demo-storage-quota" className="font-medium text-destructive">
            {t("frontend.demo.banner.storage_quota_exceeded")}
          </p>
        )}
        {showConnectivityWarning && (
          <p role="status" className="font-medium text-destructive">
            {t("frontend.demo.banner.connectivity_warning")}
          </p>
        )}
        <p>
          {demo.expiresAt && (
            <DemoCountdown expiresAt={demo.expiresAt} serverTime={demo.serverTime} />
          )}
          {" · "}
          {t("frontend.demo.banner.browser_local")}
        </p>
        <div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setResetError(false);
              setConfirmOpen(true);
            }}
            data-testid="demo-reset-trigger"
            aria-label={t("frontend.demo.banner.reset")}
            disabled={resetDisabled}
          >
            {t("frontend.demo.banner.reset")}
          </Button>
        </div>
      </AlertDescription>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("frontend.demo.banner.reset_confirm_title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("frontend.demo.banner.reset_confirm_description")}
              {resetError && (
                <span role="alert" className="mt-2 block text-destructive">
                  {t("frontend.demo.banner.reset_error")}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("frontend.master.demos.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={handleReset}>
              {t("frontend.demo.banner.reset_confirm_action")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Alert>
  );
}
