import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, KeyRound, Server } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import type { LookupExecutorEnrollment } from "../services/executor-api";

interface ExecutorCredentialsDialogProps {
  credentials: LookupExecutorEnrollment | null;
  onDismiss: () => void;
}

export function ExecutorCredentialsDialog({
  credentials,
  onDismiss,
}: ExecutorCredentialsDialogProps) {
  const [copied, setCopied] = useState<"executor_id" | "secret" | null>(null);
  const copyTimeout = useRef<number | null>(null);

  useEffect(() => {
    setCopied(null);
    return () => {
      if (copyTimeout.current !== null) window.clearTimeout(copyTimeout.current);
    };
  }, [credentials?.executor.id, credentials?.plain_secret]);

  if (!credentials) return null;

  const copiedAnnouncement = copied
    ? t(`frontend.master.executors.${copied === "secret" ? "secret" : "executor_id"}_copied`)
    : "";

  async function copyValue(kind: "executor_id" | "secret", value: string) {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      if (copyTimeout.current !== null) window.clearTimeout(copyTimeout.current);
      copyTimeout.current = window.setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error(t("frontend.master.executors.copy_error"));
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onDismiss();
      }}
    >
      <DialogContent className="w-full gap-4 p-6 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("frontend.master.executors.one_time_secret_title")}</DialogTitle>
          <DialogDescription>
            {t("frontend.master.executors.one_time_secret_description")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <CredentialRow
            icon={<Server aria-hidden="true" />}
            label={t("frontend.master.executors.executor_id")}
            value={credentials.executor.id}
            copyLabel={t("frontend.master.executors.copy_executor_id")}
            copiedLabel={t("frontend.master.executors.executor_id_copied")}
            copied={copied === "executor_id"}
            onCopy={() => void copyValue("executor_id", credentials.executor.id)}
          />
          <CredentialRow
            icon={<KeyRound aria-hidden="true" />}
            label={t("frontend.master.executors.one_time_secret")}
            value={credentials.plain_secret}
            copyLabel={t("frontend.master.executors.copy_secret")}
            copiedLabel={t("frontend.master.executors.secret_copied")}
            copied={copied === "secret"}
            onCopy={() => void copyValue("secret", credentials.plain_secret)}
          />
        </div>
        <p className="text-sm text-destructive">
          {t("frontend.master.executors.secret_dismiss_warning")}
        </p>
        <p className="sr-only" aria-live="polite">
          {copiedAnnouncement}
        </p>

        <Button type="button" onClick={onDismiss} aria-label={t("frontend.master.executors.credentials_continue")}>
          {t("frontend.master.executors.credentials_continue")}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function CredentialRow({
  icon,
  label,
  value,
  copyLabel,
  copiedLabel,
  copied,
  onCopy,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  copyLabel: string;
  copiedLabel: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="flex min-w-0 w-full max-w-full items-center gap-3 rounded-lg border p-3">
      <div className="shrink-0 text-muted-foreground">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <code className="block break-all text-sm font-medium">{value}</code>
      </div>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className="shrink-0"
        onClick={onCopy}
        aria-label={copied ? copiedLabel : copyLabel}
        title={copied ? copiedLabel : copyLabel}
      >
        {copied ? <Check data-icon="inline-start" aria-hidden="true" /> : <Copy data-icon="inline-start" aria-hidden="true" />}
      </Button>
    </div>
  );
}
