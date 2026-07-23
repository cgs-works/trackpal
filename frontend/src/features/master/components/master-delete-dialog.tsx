import { useState } from "react";
import { Loader2, AlertCircle, Trash2, Lock } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getLocale, t } from "@/i18n";
import { masterDeleteTenant } from "../services/tenant-api";

interface MasterDeleteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tenantId: string
  tenantName: string
  onSuccess: () => void
}

export function MasterDeleteDialog({
  open,
  onOpenChange,
  tenantId,
  tenantName,
  onSuccess,
}: MasterDeleteDialogProps) {
  const [password, setPassword] = useState("");
  const [confirmWord, setConfirmWord] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const destructiveWord = getLocale() === "es" ? "ELIMINAR" : "DELETE";

  function handleClose() {
    if (deleting) return;
    onOpenChange(false);
    // Reset state after animation
    setTimeout(() => {
      setPassword("");
      setConfirmWord("");
      setError(null);
    }, 200);
  }

  async function handleConfirm() {
    if (!password || !confirmWord) return;
    setDeleting(true);
    setError(null);

    try {
      await masterDeleteTenant(tenantId, password, confirmWord);
      onSuccess();
      handleClose();
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        t("frontend.my_account.danger_error");
      setError(msg);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="size-5" />
            {t("frontend.master.delete_tenant_title")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("frontend.master.delete_tenant_description", {
              name: tenantName,
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="master-delete-password">
              <Lock className="mr-1 inline size-3.5" />
              {t("frontend.my_account.danger_password_label")}
            </Label>
            <Input
              id="master-delete-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={deleting}
              autoFocus
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="master-delete-confirm-word">
              {t("frontend.my_account.danger_destructive_word_label", {
                word: destructiveWord,
              })}
            </Label>
            <Input
              id="master-delete-confirm-word"
              type="text"
              value={confirmWord}
              onChange={(e) => setConfirmWord(e.target.value)}
              placeholder={destructiveWord}
              disabled={deleting}
            />
          </div>
          {error && (
            <div className="flex items-start gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>
            {t("frontend.common.cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={
              deleting ||
              !password ||
              confirmWord !== destructiveWord
            }
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {deleting ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("frontend.my_account.danger_deleting")}
              </>
            ) : (
              t("frontend.master.delete_tenant_confirm_button")
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}