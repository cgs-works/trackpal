import { useEffect, useState, type FormEvent } from "react";
import { Copy, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
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
  mapExecutorError,
  revealLookupExecutorHostingPassword,
  type LookupExecutor,
} from "../services/executor-api";

interface ExecutorPasswordDialogProps {
  executor: LookupExecutor | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ExecutorPasswordDialog({
  executor,
  open,
  onOpenChange,
}: ExecutorPasswordDialogProps) {
  const [masterPassword, setMasterPassword] = useState("");
  const [revealedPassword, setRevealedPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) reset();
  }, [open]);

  function reset() {
    setMasterPassword("");
    setRevealedPassword("");
    setShowPassword(false);
    setSaving(false);
    setError("");
  }

  function close() {
    reset();
    onOpenChange(false);
  }

  async function reveal(event: FormEvent) {
    event.preventDefault();
    if (!executor || !masterPassword) return;

    setError("");
    setSaving(true);
    try {
      const response = await revealLookupExecutorHostingPassword(executor.id, {
        password: masterPassword,
      });
      setRevealedPassword(response.hosting_account_password);
    } catch (revealError) {
      setError(
        mapExecutorError(
          revealError,
          "frontend.master.executors.error_invalid_master_password",
        ),
      );
    } finally {
      setSaving(false);
    }
  }

  async function copyPassword() {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(revealedPassword);
      toast.success(t("frontend.master.executors.password_copied"));
    } catch {
      toast.error(t("frontend.master.executors.copy_error"));
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("frontend.master.executors.reveal_title")}</DialogTitle>
          <DialogDescription>
            {t("frontend.master.executors.reveal_warning")}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        )}

        <form onSubmit={reveal} className="flex flex-col gap-4" aria-busy={saving}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="executor-master-password">
              {t("frontend.master.executors.reveal_password")}
            </Label>
            <Input
              id="executor-master-password"
              type="password"
              value={masterPassword}
              onChange={(event) => setMasterPassword(event.target.value)}
              autoComplete="current-password"
              required
              disabled={saving || Boolean(revealedPassword)}
            />
          </div>

          {revealedPassword && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="executor-revealed-password">
                {t("frontend.master.executors.revealed_password")}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="executor-revealed-password"
                  type={showPassword ? "text" : "password"}
                  value={revealedPassword}
                  readOnly
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={t(
                    showPassword
                      ? "frontend.master.executors.hide_password"
                      : "frontend.master.executors.show_password",
                  )}
                  title={t(
                    showPassword
                      ? "frontend.master.executors.hide_password"
                      : "frontend.master.executors.show_password",
                  )}
                >
                  {showPassword ? (
                    <EyeOff data-icon="inline-start" aria-hidden="true" />
                  ) : (
                    <Eye data-icon="inline-start" aria-hidden="true" />
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={() => void copyPassword()}
                  aria-label={t("frontend.master.executors.copy_password")}
                  title={t("frontend.master.executors.copy_password")}
                >
                  <Copy data-icon="inline-start" aria-hidden="true" />
                </Button>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={saving}>
              {t("frontend.master.executors.cancel")}
            </Button>
            {!revealedPassword && (
              <Button type="submit" disabled={saving}>
                {t("frontend.master.executors.reveal_hosting_password")}
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
