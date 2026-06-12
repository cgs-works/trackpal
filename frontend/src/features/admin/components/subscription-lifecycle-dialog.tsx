import { t } from "@/i18n";
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

export type LifecycleAction = "cancel" | "renew" | "reactivate";

interface SubscriptionLifecycleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  action: LifecycleAction;
  onConfirm: () => void;
  loading?: boolean;
}

const ACTION_CONFIG: Record<
  LifecycleAction,
  {
    titleKey: string;
    confirmKey: string;
    buttonKey: string;
    buttonClass: string;
  }
> = {
  cancel: {
    titleKey: "frontend.subscriptions.cancel_title",
    confirmKey: "frontend.subscriptions.cancel_confirm",
    buttonKey: "frontend.subscriptions.yes_cancel",
    buttonClass: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  },
  renew: {
    titleKey: "frontend.subscriptions.renew_title",
    confirmKey: "frontend.subscriptions.renew_confirm",
    buttonKey: "frontend.subscriptions.yes_renew",
    buttonClass: "",
  },
  reactivate: {
    titleKey: "frontend.subscriptions.reactivate_title",
    confirmKey: "frontend.subscriptions.reactivate_confirm",
    buttonKey: "frontend.subscriptions.yes_reactivate",
    buttonClass: "",
  },
};

export function SubscriptionLifecycleDialog({
  open,
  onOpenChange,
  action,
  onConfirm,
  loading = false,
}: SubscriptionLifecycleDialogProps) {
  const config = ACTION_CONFIG[action];

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t(config.titleKey)}</AlertDialogTitle>
          <AlertDialogDescription>
            {t(config.confirmKey)}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>
            {t("frontend.common.cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={loading}
            className={config.buttonClass}
          >
            {loading ? t("frontend.subscriptions.saving") : t(config.buttonKey)}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
