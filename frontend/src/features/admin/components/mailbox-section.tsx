import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Mail, CheckCircle2, AlertCircle, Unplug } from "lucide-react";
import { t } from "@/i18n";
import {
  type Mailbox,
  getMailbox,
  upsertMailbox,
  testMailbox,
  startOAuth,
  disconnectMailbox,
} from "../services/settings-api";

const PROVIDER_OPTIONS = [
  { value: "google", label: t("frontend.mailbox.connect_google") },
  { value: "microsoft", label: t("frontend.mailbox.connect_microsoft") },
  { value: "imap_custom", label: t("frontend.mailbox.template_custom") },
];

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, { label: string; icon: typeof CheckCircle2; className: string }> = {
    connected: {
      label: t("frontend.mailbox.status_connected"),
      icon: CheckCircle2,
      className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    },
    error: {
      label: t("frontend.mailbox.status_error"),
      icon: AlertCircle,
      className: "bg-destructive/10 text-destructive",
    },
    disconnected: {
      label: t("frontend.mailbox.status_disconnected"),
      icon: AlertCircle,
      className: "bg-muted text-muted-foreground",
    },
  };
  const config = variants[status] || variants.disconnected;
  const Icon = config.icon;
  return (
    <Badge variant="secondary" className={config.className}>
      <Icon className="size-3 mr-1" />
      {config.label}
    </Badge>
  );
}

export function MailboxSection() {
  const [mailbox, setMailbox] = useState<Mailbox | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Form state
  const [provider, setProvider] = useState("google");
  const [email, setEmail] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [imapSsl, setImapSsl] = useState(true);
  const [imapPassword, setImapPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const loadMailbox = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await getMailbox();
      setMailbox(data);
      if (data) {
        setProvider(data.provider);
        setEmail(data.mailbox_email);
        setImapHost(data.imap_host || "");
        setImapPort(String(data.imap_port || 993));
        setImapSsl(data.imap_ssl ?? true);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.mailbox.error_load")
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMailbox();
  }, [loadMailbox]);

  // ── OAuth connect ─────────────────────────────────────────
  async function handleOAuthConnect(prov: "google" | "microsoft") {
    try {
      const { auth_url } = await startOAuth(prov);
      window.open(auth_url, "_blank", "width=500,height=600");
      toast.info(t("frontend.mailbox.oauth_started"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_oauth")
      );
    }
  }

  // ── IMAP save ─────────────────────────────────────────────
  async function handleSaveImap(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const data = await upsertMailbox({
        provider: "imap_custom",
        mailbox_email: email,
        imap_host: imapHost,
        imap_port: parseInt(imapPort, 10),
        imap_ssl: imapSsl,
        imap_password: imapPassword,
      });
      setMailbox(data);
      toast.success(t("frontend.mailbox.success_saved"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_save")
      );
    } finally {
      setSaving(false);
    }
  }

  // ── Test connection ───────────────────────────────────────
  async function handleTest() {
    setTesting(true);
    try {
      const result = await testMailbox();
      if (result.success) {
        toast.success(result.message);
        await loadMailbox();
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_test")
      );
    } finally {
      setTesting(false);
    }
  }

  // ── Disconnect ────────────────────────────────────────────
  async function handleDisconnect() {
    try {
      await disconnectMailbox();
      setMailbox(null);
      toast.success(t("frontend.mailbox.success_disconnected"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_disconnect")
      );
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="h-32 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Current status */}
      {mailbox && (
        <div className="flex items-center justify-between p-4 rounded-lg border bg-card">
          <div className="flex items-center gap-3">
            <Mail className="size-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{mailbox.mailbox_email}</p>
              <p className="text-xs text-muted-foreground">
                {mailbox.provider === "imap_custom"
                  ? `IMAP · ${mailbox.imap_host}`
                  : mailbox.provider.charAt(0).toUpperCase() + mailbox.provider.slice(1)}
                {mailbox.auth_method === "oauth" && " · OAuth"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={mailbox.status} />
            <Button variant="ghost" size="sm" onClick={handleDisconnect}>
              <Unplug className="size-3.5 mr-1" />
              {t("frontend.mailbox.disconnect")}
            </Button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && !mailbox && (
        <div className="text-sm text-muted-foreground text-center py-4">
          {t("frontend.mailbox.not_configured")}
        </div>
      )}

      {/* Provider selection */}
      {!mailbox && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t("frontend.mailbox.provider")}</Label>
            <Select value={provider} onValueChange={(v) => setProvider(v ?? "")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDER_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* OAuth option */}
          {provider !== "imap_custom" && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="oauth_email">{t("frontend.mailbox.email")}</Label>
                <Input
                  id="oauth_email"
                  type="email"
                  required
                  placeholder={t("frontend.subscriptions.placeholder_email")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <Button
                onClick={() =>
                  handleOAuthConnect(provider as "google" | "microsoft")
                }
                disabled={!email}
                className="w-full"
              >
                {t("frontend.mailbox.connect_oauth")}
              </Button>
            </div>
          )}

          {/* IMAP option */}
          {provider === "imap_custom" && (
            <form onSubmit={handleSaveImap} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="imap_email">{t("frontend.mailbox.email")}</Label>
                <Input
                  id="imap_email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="imap_host">{t("frontend.mailbox.imap_host")}</Label>
                  <Input
                    id="imap_host"
                    required
                    placeholder="imap.example.com"
                    value={imapHost}
                    onChange={(e) => setImapHost(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="imap_port">{t("frontend.mailbox.imap_port")}</Label>
                  <Input
                    id="imap_port"
                    type="number"
                    required
                    value={imapPort}
                    onChange={(e) => setImapPort(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Switch
                  id="imap_ssl"
                  checked={imapSsl}
                  onCheckedChange={setImapSsl}
                />
                <Label htmlFor="imap_ssl" className="cursor-pointer">
                  {t("frontend.mailbox.imap_ssl")}
                </Label>
              </div>

              <div className="space-y-2">
                <Label htmlFor="imap_password">{t("frontend.mailbox.imap_password")}</Label>
                <Input
                  id="imap_password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={imapPassword}
                  onChange={(e) => setImapPassword(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  {t("frontend.mailbox.imap_form_help")}
                </p>
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={saving}>
                  {saving ? t("frontend.mailbox.saving") : t("frontend.mailbox.save_imap")}
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Test connection */}
      {mailbox && mailbox.auth_method === "imap_app_password" && (
        <div className="flex justify-end">
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? t("frontend.mailbox.testing") : t("frontend.mailbox.test")}
          </Button>
        </div>
      )}
    </div>
  );
}
