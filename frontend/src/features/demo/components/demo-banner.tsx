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

export function DemoBanner({
  showConnectivityWarning = false,
}: {
  showConnectivityWarning?: boolean;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const demo = useAuthStore((s) => s.demo);
  const dataSource = useAuthStore((s) => s.dataSource);

  if (!demo || demo.status !== "active") return null;
  const activeDemo = demo;

  function handleReset() {
    dataSource.workspace?.reset(activeDemo);
    setConfirmOpen(false);
    window.location.reload();
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
            onClick={() => setConfirmOpen(true)}
            data-testid="demo-reset-trigger"
            aria-label={t("frontend.demo.banner.reset")}
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
