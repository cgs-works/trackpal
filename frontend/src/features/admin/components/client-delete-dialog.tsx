import { t } from "@/i18n";
import type { DeletePreview } from "../services/catalog-api";
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

interface DeleteConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  clientName: string;
  preview: DeletePreview | null;
  loading: boolean;
  error: string;
  onConfirm: () => void;
}

export function DeleteConfirmDialog({
  open,
  onOpenChange,
  clientName,
  preview,
  loading,
  error,
  onConfirm,
}: DeleteConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("frontend.clients.confirm_delete", { name: clientName })}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("frontend.clients.delete_warning", { name: clientName })}
          </AlertDialogDescription>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {loading ? (
            <p className="text-sm text-muted-foreground">{t("frontend.catalog.delete_preview_loading")}</p>
          ) : preview ? (
            <div className="grid grid-cols-3 gap-2 text-center text-sm">
              <div className="rounded-md bg-muted p-2">
                <strong className="block text-lg">{preview.active_subscription_count}</strong>
                {t("frontend.catalog.active_subscriptions")}
              </div>
              <div className="rounded-md bg-muted p-2">
                <strong className="block text-lg">{preview.historical_subscription_count}</strong>
                {t("frontend.catalog.historical_subscriptions")}
              </div>
              <div className="rounded-md bg-muted p-2">
                <strong className="block text-lg">{preview.total_subscription_count}</strong>
                {t("frontend.catalog.total_subscriptions")}
              </div>
            </div>
          ) : null}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("frontend.common.cancel")}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={loading || !preview}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {t("frontend.clients.delete")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
