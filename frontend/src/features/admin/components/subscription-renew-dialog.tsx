import { useState } from "react";
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
import { type Subscription } from "../services/subscription-api";

interface SubscriptionRenewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subscription: Subscription | null;
  onConfirm: (durationType: string) => void;
  loading?: boolean;
}

const DURATION_OPTIONS = [
  { value: "1_month", label: "1 month", days: 30 },
  { value: "3_months", label: "3 months", days: 90 },
  { value: "9_months", label: "9 months", days: 270 },
  { value: "1_year", label: "1 year", days: 365 },
];

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function SubscriptionRenewDialog({
  open,
  onOpenChange,
  subscription,
  onConfirm,
  loading = false,
}: SubscriptionRenewDialogProps) {
  const [step, setStep] = useState<"duration" | "confirm">("duration");
  const [selectedDuration, setSelectedDuration] = useState("1_month");

  if (!subscription) return null;

  function handleOpenChange(value: boolean) {
    if (!value) {
      setStep("duration");
      setSelectedDuration("1_month");
    }
    onOpenChange(value);
  }

  function handleNext() {
    setStep("confirm");
  }

  function handleConfirm() {
    onConfirm(selectedDuration);
  }

  const selectedOption = DURATION_OPTIONS.find((o) => o.value === selectedDuration);
  const newExpiry = selectedOption
    ? addDays(subscription.expires_at, selectedOption.days)
    : "";

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        {step === "duration" ? (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("frontend.subscriptions.renew_title")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                Select the renewal duration for this subscription.
              </AlertDialogDescription>
            </AlertDialogHeader>

            <div className="grid grid-cols-2 gap-2 py-4">
              {DURATION_OPTIONS.map((opt) => {
                const newDate = addDays(subscription.expires_at, opt.days);
                const isSelected = selectedDuration === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setSelectedDuration(opt.value)}
                    className={`flex flex-col items-center gap-1 rounded-lg border p-3 transition-colors ${
                      isSelected
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <span className="font-medium text-sm">{opt.label}</span>
                    <span className="text-xs text-muted-foreground">→ {newDate}</span>
                  </button>
                );
              })}
            </div>

            <AlertDialogFooter>
              <AlertDialogCancel>{t("frontend.common.cancel")}</AlertDialogCancel>
              <AlertDialogAction onClick={handleNext}>
                Next
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        ) : (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("frontend.subscriptions.renew_title")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to renew this subscription for{" "}
                <strong>{selectedOption?.label}</strong>?
                <br />
                <br />
                Current expiry:{" "}
                <span className="font-mono">
                  {new Date(subscription.expires_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <br />
                New expiry:{" "}
                <span className="font-mono text-green-500">{newExpiry}</span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel
                onClick={() => setStep("duration")}
                disabled={loading}
              >
                Back
              </AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirm} disabled={loading}>
                {loading
                  ? t("frontend.subscriptions.renewing")
                  : t("frontend.subscriptions.yes_renew")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
