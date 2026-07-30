import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Mail,
  CheckCircle2,
  AlertCircle,
  Unplug,
  HelpCircle,
  Loader2,
} from "lucide-react";
import { t } from "@/i18n";
import {
  connectGmail,
  testMailbox,
  startGoogleOAuth,
  disconnectMailbox,
  type GmailAppPasswordConnect,
  type Mailbox,
} from "../services/settings-api";
import { useSettingsStore } from "@/store/settings";
import { useAuthStore } from "@/store/auth";
import { isGmailOAuthConnectEnabled } from "../mailbox-config";
import {
  GmailSetupAssistant,
  type GmailAppPasswordConnect as AssistantConnectPayload,
} from "./gmail-setup-assistant";

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

function mailboxErrorMessage(error: unknown): string {
  const detail = (error as any)?.response?.data?.detail;
  if (detail === "gmail_app_password_rejected") {
    return t("frontend.mailbox.error_app_password_rejected");
  }
  if (detail === "gmail_connection_unavailable") {
    return t("frontend.mailbox.error_connection_unavailable");
  }
  if (error instanceof Error) return error.message;
  return t("frontend.mailbox.error_save");
}

function methodLabel(auth_method: string): string {
  if (auth_method === "oauth") return t("frontend.mailbox.method_google_connection");
  if (auth_method === "app_password") return t("frontend.mailbox.method_app_password");
  return auth_method;
}

export function MailboxSection() {
  const { dataSource } = useAuthStore();
  const { mailbox, mailboxLoaded, loadMailbox } = useSettingsStore();
  const isDemo = dataSource.mode === "demo";
  const [isLoading, setIsLoading] = useState(!mailboxLoaded);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const channelRef = useRef<BroadcastChannel | null>(null);

  const oauthConnectEnabled = isGmailOAuthConnectEnabled();
  const [oauthStep, setOauthStep] = useState<"idle" | "consent">("idle");
  const [oauthConsentAccepted, setOauthConsentAccepted] = useState(false);

  const loadMailboxData = useCallback(async () => {
    if (mailboxLoaded) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      await loadMailbox(dataSource.settings);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.mailbox.error_load")
      );
    } finally {
      setIsLoading(false);
    }
  }, [dataSource.settings, loadMailbox, mailboxLoaded]);

  useEffect(() => {
    loadMailboxData();
  }, [loadMailboxData]);

  // ── Listen for OAuth popup completion via BroadcastChannel ──
  useEffect(() => {
    const ch = new BroadcastChannel("trackpal_oauth");
    channelRef.current = ch;
    ch.onmessage = async (ev) => {
      if (ev.data === "mailbox_oauth_success") {
        useSettingsStore.getState().clearSettingsCache();
        await loadMailboxData();
        toast.success(t("frontend.mailbox.oauth_connected"));
      }
    };
    return () => {
      ch.close();
      channelRef.current = null;
    };
  }, [loadMailboxData]);

  // ── App-password connect ──────────────────────────────────
  async function handleConnectAppPassword(
    payload: AssistantConnectPayload,
  ): Promise<boolean> {
    try {
      await connectGmail(payload);
      useSettingsStore.getState().clearSettingsCache();
      await loadMailboxData();
      toast.success(t("frontend.mailbox.success_connected"));
      return true;
    } catch (err) {
      toast.error(mailboxErrorMessage(err));
      return false;
    }
  }

  // ── OAuth connect ─────────────────────────────────────────
  async function handleOAuthStart() {
    if (!oauthConsentAccepted) return;
    try {
      const { auth_url } = await startGoogleOAuth();
      window.open(auth_url, "_blank", "width=500,height=600");
      setOauthConsentAccepted(false);
      setOauthStep("idle");
      toast.info(t("frontend.mailbox.oauth_started"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.mailbox.error_oauth")
      );
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
                {methodLabel(mailbox.auth_method)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={mailbox.status} />
            {!isDemo && (
              <Button variant="ghost" size="sm" onClick={handleDisconnect} disabled={disconnecting}>
                {disconnecting ? (
                  <Loader2 className="size-3.5 mr-1 animate-spin" />
                ) : (
                  <Unplug className="size-3.5 mr-1" />
                )}
                {disconnecting ? t("frontend.mailbox.disconnecting") : t("frontend.mailbox.disconnect")}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Error when mailbox exists */}
      {error && mailbox && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg p-3">
          {error}
        </div>
      )}

      {/* Not configured message */}
      {error && !mailbox && (
        <div className="text-sm text-muted-foreground text-center py-4">
          {t("frontend.mailbox.not_configured")}
        </div>
      )}

      {/* Setup assistant */}
      {!mailbox && !isDemo && (
        <div className="space-y-4">
          {/* Optional OAuth path */}
          {oauthConnectEnabled && (
            <div className="space-y-3">
              {oauthStep === "idle" && (
                <Button
                  variant="outline"
                  onClick={() => setOauthStep("consent")}
                  className="w-full"
                >
                  {t("frontend.mailbox.use_google_connection")}
                </Button>
              )}

              {oauthStep === "consent" && (
                <div className="space-y-3">
                  <button
                    type="button"
                    onClick={() => {
                      setOauthStep("idle");
                      setOauthConsentAccepted(false);
                    }}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    ← {t("frontend.mailbox.back")}
                  </button>
                  <div
                    id="mailbox-oauth-consent-description"
                    className="space-y-3 rounded-lg border bg-muted/30 p-4"
                  >
                    <h3 className="text-sm font-medium">
                      {t("frontend.mailbox.oauth_consent_title")}
                    </h3>
                    <div className="space-y-2 text-sm text-muted-foreground">
                      <p>{t("frontend.mailbox.oauth_consent_data")}</p>
                      <p>{t("frontend.mailbox.oauth_consent_transfer")}</p>
                      <p>{t("frontend.mailbox.oauth_consent_storage")}</p>
                    </div>
                    <a
                      href="https://trackpal.wilfredocamacho.dev/privacy-policy"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex text-sm font-medium text-primary underline-offset-4 hover:underline"
                    >
                      {t("frontend.mailbox.oauth_consent_privacy")}
                    </a>
                    <label className="flex cursor-pointer items-start gap-3 rounded-md border bg-background p-3 text-sm">
                      <input
                        type="checkbox"
                        checked={oauthConsentAccepted}
                        onChange={(event) => setOauthConsentAccepted(event.target.checked)}
                        aria-describedby="mailbox-oauth-consent-description"
                        className="mt-0.5 size-4 shrink-0 accent-primary"
                      />
                      <span>{t("frontend.mailbox.oauth_consent_checkbox")}</span>
                    </label>
                  </div>
                  <Button
                    onClick={handleOAuthStart}
                    disabled={!oauthConsentAccepted}
                    className="w-full"
                  >
                    {t("frontend.mailbox.continue_google")}
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* App-password assistant */}
          <GmailSetupAssistant
            oauthConnectEnabled={oauthConnectEnabled}
            onConnect={handleConnectAppPassword}
            onStartOAuth={async () => {
              setOauthStep("consent");
            }}
          />
        </div>
      )}

      {/* Test connection */}
      {mailbox && !isDemo && (
        <div className="flex justify-end">
          <Button variant="outline" onClick={handleTest} disabled={testing}>
            {testing ? t("frontend.mailbox.testing") : t("frontend.mailbox.test")}
          </Button>
        </div>
      )}
    </div>
  );
}
