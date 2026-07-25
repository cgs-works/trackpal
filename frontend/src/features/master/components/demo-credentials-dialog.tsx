import { useState } from "react";
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

  if (!credentials) return null;

  async function copyValue(kind: "username" | "password", value: string) {
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 1500);
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
      <DialogContent className="sm:max-w-md">
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
            copied={copied === "username"}
            onCopy={() => copyValue("username", credentials.username)}
          />
          <CredentialRow
            icon={<KeyRound />}
            label={t("frontend.master.demos.password_label")}
            value={credentials.plain_password}
            copyLabel={t("frontend.master.demos.copy_password")}
            copied={copied === "password"}
            onCopy={() => copyValue("password", credentials.plain_password)}
          />
        </div>

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
  copied,
  onCopy,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  copyLabel: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border p-3">
      <div className="text-muted-foreground">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <code className="block truncate text-sm font-medium">{value}</code>
      </div>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        onClick={onCopy}
        aria-label={copyLabel}
        title={copyLabel}
      >
        {copied ? <Check /> : <Copy />}
      </Button>
    </div>
  );
}
