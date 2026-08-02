import { useEffect, useState, type FormEvent } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";
import {
  deleteLookupExecutor,
  disableLookupExecutor,
  enableLookupExecutor,
  mapExecutorError,
  rotateLookupExecutorSecret,
  testLookupExecutor,
  verifyLookupExecutor,
  type LookupExecutor,
  type LookupExecutorEnrollment,
} from "../services/executor-api";
import { ExecutorCredentialsDialog } from "./executor-credentials-dialog";
import { ExecutorPasswordDialog } from "./executor-password-dialog";

export type ExecutorAction =
  | "verify"
  | "test"
  | "enable"
  | "disable"
  | "rotate"
  | "reveal"
  | "delete";

interface ExecutorActionDialogsProps {
  action: ExecutorAction | null;
  executor: LookupExecutor | null;
  onClose: () => void;
  onCompleted: (executor?: LookupExecutor) => void;
}

export function ExecutorActionDialogs({
  action,
  executor,
  onClose,
  onCompleted,
}: ExecutorActionDialogsProps) {
  const [credentials, setCredentials] = useState<LookupExecutorEnrollment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [masterPassword, setMasterPassword] = useState("");

  const open = Boolean(action && executor);
  const isHttp = executor?.transport_mode === "http_encrypted";

  useEffect(() => {
    setCredentials(null);
    setLoading(false);
    setError("");
    setConfirmation("");
    setMasterPassword("");
  }, [action, executor?.id]);

  function close() {
    setCredentials(null);
    setError("");
    setConfirmation("");
    setMasterPassword("");
    onClose();
  }

  async function performAction(event?: FormEvent) {
    event?.preventDefault();
    if (!action || !executor || loading) return;
    if (action === "delete" && executor.active_jobs > 0) return;

    if (action === "verify") {
      if (isHttp && confirmation !== "ALLOW HTTP") {
        setError("frontend.master.executors.error_insecure_http_confirmation_required");
        return;
      }
      if (isHttp && !masterPassword) {
        setError("frontend.master.executors.error_invalid_master_password");
        return;
      }
    }

    setError("");
    setLoading(true);
    try {
      if (action === "verify") {
        const result = isHttp
          ? await verifyLookupExecutor(executor.id, {
              confirmation: "ALLOW HTTP",
              password: masterPassword,
            })
          : await verifyLookupExecutor(executor.id);
        onCompleted(result);
        close();
      } else if (action === "test") {
        const result = await testLookupExecutor(executor.id);
        onCompleted(result.executor);
        close();
      } else if (action === "enable") {
        const result = await enableLookupExecutor(executor.id);
        onCompleted(result);
        close();
      } else if (action === "disable") {
        const result = await disableLookupExecutor(executor.id);
        onCompleted(result);
        close();
      } else if (action === "rotate") {
        const result = await rotateLookupExecutorSecret(executor.id);
        setCredentials(result);
        onCompleted(result.executor);
        setLoading(false);
      } else if (action === "delete") {
        if (executor.active_jobs > 0) return;
        await deleteLookupExecutor(executor.id);
        onCompleted();
        close();
      }
    } catch (actionError) {
      setError(
        mapExecutorError(
          actionError,
          `frontend.master.executors.error_${action}`,
        ),
      );
      setLoading(false);
    }
  }

  if (action === "reveal") {
    return (
      <ExecutorPasswordDialog
        executor={executor}
        open={open}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) onClose();
        }}
      />
    );
  }

  if (!action || !executor) return null;

  if (action === "verify" && isHttp) {
    return (
      <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("frontend.master.executors.verify")}</DialogTitle>
            <DialogDescription>
              {t("frontend.master.executors.transport_warning")}
            </DialogDescription>
          </DialogHeader>
          <ActionError error={error} />
          <form onSubmit={(event) => void performAction(event)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="executor-http-confirmation">
                {t("frontend.master.executors.http_confirmation")}
              </Label>
              <Input
                id="executor-http-confirmation"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="ALLOW HTTP"
                autoComplete="off"
                required
                disabled={loading}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="executor-http-master-password">
                {t("frontend.master.executors.reveal_password")}
              </Label>
              <Input
                id="executor-http-master-password"
                type="password"
                value={masterPassword}
                onChange={(event) => setMasterPassword(event.target.value)}
                autoComplete="current-password"
                required
                disabled={loading}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={close} disabled={loading}>
                {t("frontend.master.executors.cancel")}
              </Button>
              <Button type="submit" disabled={loading}>
                {t("frontend.master.executors.verify")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    );
  }

  if (action === "verify") {
    return (
      <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("frontend.master.executors.verify")}</DialogTitle>
            <DialogDescription>
              {t("frontend.master.executors.connection_healthy")}
            </DialogDescription>
          </DialogHeader>
          <ActionError error={error} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={loading}>
              {t("frontend.master.executors.cancel")}
            </Button>
            <Button type="button" onClick={() => void performAction()} disabled={loading}>
              {t("frontend.master.executors.verify")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  const destructive = action === "delete" || action === "disable";
  const blocked = action === "delete" && executor.active_jobs > 0;

  return (
    <>
      <AlertDialog open={open && !credentials} onOpenChange={(nextOpen) => !nextOpen && close()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t(`frontend.master.executors.${actionTitleKey[action]}`)}</AlertDialogTitle>
          <AlertDialogDescription>
            {t(`frontend.master.executors.${actionDescriptionKey[action]}`)}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <ActionError error={error} />
        {action === "test" && (
          <p className="rounded-lg border p-3 text-sm text-muted-foreground">
            {t("frontend.master.executors.test_warning")}
          </p>
        )}
        {blocked && (
          <p role="alert" className="text-sm text-destructive">
            {t("frontend.master.executors.error_active_jobs")}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>
            {t("frontend.master.executors.cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={loading || blocked}
            className={destructive ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : undefined}
            onClick={(event) => {
              event.preventDefault();
              void performAction();
            }}
          >
            {t("frontend.master.executors.confirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
      </AlertDialog>
      <ExecutorCredentialsDialog
        credentials={credentials}
        onDismiss={() => {
          setCredentials(null);
          close();
        }}
      />
    </>
  );
}

function ActionError({ error }: { error: string }) {
  if (!error) return null;
  return <p role="alert" className="text-sm text-destructive">{t(error)}</p>;
}

const actionTitleKey: Record<Exclude<ExecutorAction, "reveal" | "verify">, string> = {
  test: "test",
  enable: "enable",
  disable: "disable",
  rotate: "rotate_secret",
  delete: "delete",
};

const actionDescriptionKey: Record<Exclude<ExecutorAction, "reveal" | "verify">, string> = {
  test: "test_description",
  enable: "enable_description",
  disable: "disable_description",
  rotate: "rotate_description",
  delete: "delete_description",
};

