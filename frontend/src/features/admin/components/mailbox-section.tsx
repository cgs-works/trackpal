import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

import { toast } from "sonner";
import { Mail, CheckCircle2, AlertCircle, Unplug, HelpCircle, Loader2, ShieldCheck, Inbox, Server } from "lucide-react";
import { t } from "@/i18n";
import {
  upsertMailbox,
  testMailbox,
  startOAuth,
  disconnectMailbox,
} from "../services/settings-api";
import { useSettingsStore } from "@/store/settings";

const PROVIDER_OPTIONS = [
  {
    value: "google",
    label: t("frontend.mailbox.connect_google"),
    description: t("frontend.mailbox.product_tooltip"),
    icon: Inbox,
    badge: "OAuth",
  },
  {
    value: "microsoft",
    label: t("frontend.mailbox.connect_microsoft"),
    description: t("frontend.mailbox.product_tooltip"),
    icon: ShieldCheck,
    badge: "OAuth",
  },
  {
    value: "imap_custom",
    label: t("frontend.mailbox.template_custom"),
    description: t("frontend.mailbox.template_custom_hint"),
    icon: Server,
    badge: null,
  },
] as const;

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
  const { mailbox, mailboxLoaded, loadMailbox } = useSettingsStore();
  const [isLoading, setIsLoading] = useState(!mailboxLoaded);
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
  const [disconnecting, setDisconnecting] = useState(false);

  const loadMailboxData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await loadMailbox();
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
  }, [loadMailbox]);

  useEffect(() => {
    loadMailboxData();
  }, [loadMailboxData]);

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
      await upsertMailbox({
        provider: "imap_custom",
        mailbox_email: email,
        imap_host: imapHost,
        imap_port: parseInt(imapPort, 10),
        imap_ssl: imapSsl,
        imap_password: imapPassword,
      });
      useSettingsStore.getState().clearSettingsCache();
      await loadMailboxData();
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
        useSettingsStore.getState().clearSettingsCache();
        await loadMailboxData();
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
    setDisconnecting(true);
    try {
      await disconnectMailbox();
      useSettingsStore.getState().clearSettingsCache();
      await loadMailboxData();
      toast.success(t("frontend.mailbox.success_disconnected"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_disconnect")
      );
    } finally {
      setDisconnecting(false);
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
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-medium">{t("frontend.mailbox.section_title")}</h2>
          <p className="text-sm text-muted-foreground">{t("frontend.mailbox.product_description")}</p>
        </div>
        <span title={t("frontend.mailbox.product_tooltip")}>
          <HelpCircle className="size-4 text-muted-foreground" />
        </span>
      </div>

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
                  : PROVIDER_OPTIONS.find((o) => o.value === mailbox.provider)?.label ?? mailbox.provider}
                {mailbox.auth_method === "oauth" && " · OAuth"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={mailbox.status} />
            <Button variant="ghost" size="sm" onClick={handleDisconnect} disabled={disconnecting}>
              {disconnecting ? (
                <Loader2 className="size-3.5 mr-1 animate-spin" />
              ) : (
                <Unplug className="size-3.5 mr-1" />
              )}
              {disconnecting ? t("frontend.mailbox.disconnecting") : t("frontend.mailbox.disconnect")}
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {PROVIDER_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const isSelected = provider === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setProvider(opt.value)}
                  className={
                    "relative flex flex-col items-center gap-2 p-4 rounded-lg border text-left transition-colors " +
                    (isSelected
                      ? "border-primary/50 bg-primary/5"
                      : "border-border hover:border-muted-foreground/30")
                  }
                >
                  <div className={
                    "size-10 rounded-full flex items-center justify-center transition-colors " +
                    (isSelected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")
                  }>
                    <Icon className="size-5" />
                  </div>
                  <span className="text-sm font-medium text-foreground">{opt.label}</span>
                  <span className="text-xs text-muted-foreground text-center leading-snug">
                    {opt.description}
                  </span>
                  {opt.badge && (
                    <span className="absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                      {opt.badge}
                    </span>
                  )}
                </button>
              );
            })}
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
                  placeholder={t("frontend.mailbox.email")}
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

      {/* Error when mailbox exists */}
      {error && mailbox && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg p-3">
          {error}
        </div>
      )}

      {/* Test connection */}
      {mailbox && (
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
