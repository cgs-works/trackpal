import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, KeyRound, UserRound } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import type { DemoTenantCredentials } from "../services/demo-api";

interface DemoCredentialsDialogProps {
  credentials: DemoTenantCredentials | null;
  onDismiss: () => void;
}

export function DemoCredentialsDialog({
  credentials,
  onDismiss,
}: DemoCredentialsDialogProps) {
  const [copied, setCopied] = useState<"username" | "password" | null>(null);
  const copyTimeout = useRef<number | null>(null);

  useEffect(() => {
    setCopied(null);
    return () => {
      if (copyTimeout.current !== null) window.clearTimeout(copyTimeout.current);
    };
  }, [credentials?.username, credentials?.plain_password]);

  if (!credentials) return null;

  const copiedAnnouncement = copied
    ? t(`frontend.master.demos.copied_${copied}`)
    : "";

  async function copyValue(kind: "username" | "password", value: string) {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      if (copyTimeout.current !== null) window.clearTimeout(copyTimeout.current);
      copyTimeout.current = window.setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error(t("frontend.master.demos.copy_error"));
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          setCopied(null);
          onDismiss();
        }
      }}
    >
      <DialogContent className="w-full gap-4 p-6 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("frontend.master.demos.credentials_title")}</DialogTitle>
          <DialogDescription>
            {t("frontend.master.demos.credentials_description", {
              name: credentials.name,
            })}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <CredentialRow
            icon={<UserRound />}
            label={t("frontend.master.demos.username_label")}
            value={credentials.username}
            copyLabel={t("frontend.master.demos.copy_username")}
            copiedLabel={t("frontend.master.demos.copied_username")}
            copied={copied === "username"}
            onCopy={() => copyValue("username", credentials.username)}
          />
          <CredentialRow
            icon={<KeyRound />}
            label={t("frontend.master.demos.password_label")}
            value={credentials.plain_password}
            copyLabel={t("frontend.master.demos.copy_password")}
            copiedLabel={t("frontend.master.demos.copied_password")}
            copied={copied === "password"}
            onCopy={() => copyValue("password", credentials.plain_password)}
          />
        </div>
        <p className="sr-only" aria-live="polite">
          {copiedAnnouncement}
        </p>

        <Button onClick={onDismiss} aria-label={t("frontend.master.demos.dismiss_credentials")}>
          {t("frontend.master.demos.done")}
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
        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      </Button>
    </div>
  );
}
