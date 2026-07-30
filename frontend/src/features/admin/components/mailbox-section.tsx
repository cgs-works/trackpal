import { useState, useEffect, useCallback } from "react";
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
import { GmailSetupAssistant } from "./gmail-setup-assistant";

function StatusBadge({ status }: { status: string }) {
  const variants: Record<
    string,
    { label: string; icon: typeof CheckCircle2; className: string }
  > = {
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
  const detail = (
    error as { response?: { data?: { detail?: unknown } } }
  ).response?.data?.detail;
  if (detail === "gmail_app_password_rejected") {
    return t("frontend.mailbox.error_app_password_rejected");
  }
  if (detail === "gmail_connection_unavailable") {
    return t("frontend.mailbox.error_connection_unavailable");
  }
  return t("frontend.mailbox.error_save");
}

function methodLabel(authMethod: string): string {
  if (authMethod === "oauth") {
    return t("frontend.mailbox.method_google_connection");
  }
  if (authMethod === "app_password") {
    return t("frontend.mailbox.method_app_password");
  }
  return authMethod;
}

interface MailboxStatusCardProps {
  mailbox: Mailbox;
  isDemo: boolean;
  disconnecting: boolean;
  onDisconnect(): Promise<void>;
}

function MailboxStatusCard({
  mailbox,
  isDemo,
  disconnecting,
  onDisconnect,
}: MailboxStatusCardProps) {
  return (
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
          <Button
            variant="ghost"
            size="sm"
            onClick={onDisconnect}
            disabled={disconnecting}
          >
            {disconnecting ? (
              <Loader2 className="size-3.5 mr-1 animate-spin" />
            ) : (
              <Unplug className="size-3.5 mr-1" />
            )}
            {disconnecting
              ? t("frontend.mailbox.disconnecting")
              : t("frontend.mailbox.disconnect")}
          </Button>
        )}
      </div>
    </div>
  );
}

interface MailboxConfigurationProps {
  mailbox: Mailbox | null;
  error: string;
  isDemo: boolean;
  oauthConnectEnabled: boolean;
  disconnecting: boolean;
  testing: boolean;
  onConnect(payload: GmailAppPasswordConnect): Promise<boolean>;
  onStartOAuth(): Promise<void>;
  onDisconnect(): Promise<void>;
  onTest(): Promise<void>;
}

function MailboxConfiguration({
  mailbox,
  error,
  isDemo,
  oauthConnectEnabled,
  disconnecting,
  testing,
  onConnect,
  onStartOAuth,
  onDisconnect,
  onTest,
}: MailboxConfigurationProps) {
  if (!mailbox) {
    return (
      <>
        {error && (
          <div className="text-sm text-muted-foreground text-center py-4">
            {t("frontend.mailbox.not_configured")}
          </div>
        )}
        {!isDemo && (
          <GmailSetupAssistant
            oauthConnectEnabled={oauthConnectEnabled}
            onConnect={onConnect}
            onStartOAuth={onStartOAuth}
          />
        )}
      </>
    );
  }

  return (
    <>
      <MailboxStatusCard
        mailbox={mailbox}
        isDemo={isDemo}
        disconnecting={disconnecting}
        onDisconnect={onDisconnect}
      />
      {error && (
        <div className="text-sm text-destructive bg-destructive/10 rounded-lg p-3">
          {error}
        </div>
      )}
      {!isDemo && (
        <div className="flex justify-end">
          <Button variant="outline" onClick={onTest} disabled={testing}>
            {testing
              ? t("frontend.mailbox.testing")
              : t("frontend.mailbox.test")}
          </Button>
        </div>
      )}
    </>
  );
}

export function MailboxSection() {
  const { dataSource } = useAuthStore();
  const { mailbox, mailboxLoaded, loadMailbox } = useSettingsStore();
  const isDemo = dataSource.mode === "demo";
  const [isLoading, setIsLoading] = useState(!mailboxLoaded);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const oauthConnectEnabled = isGmailOAuthConnectEnabled();

  const loadMailboxData = useCallback(async () => {
    if (useSettingsStore.getState().mailboxLoaded) {
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
  }, [dataSource.settings, loadMailbox]);

  useEffect(() => {
    loadMailboxData();
  }, [loadMailboxData]);

  const refreshMailbox = useCallback(async () => {
    useSettingsStore.getState().clearSettingsCache();
    await loadMailboxData();
  }, [loadMailboxData]);

  // ── Listen for OAuth popup completion via BroadcastChannel ──
  useEffect(() => {
    const channel = new BroadcastChannel("trackpal_oauth");
    channel.onmessage = async (event) => {
      if (event.data === "mailbox_oauth_success") {
        await refreshMailbox();
        toast.success(t("frontend.mailbox.oauth_connected"));
      }
    };
    return () => channel.close();
  }, [refreshMailbox]);

  // ── App-password connect ──────────────────────────────────
  async function handleConnectAppPassword(
    payload: GmailAppPasswordConnect,
  ): Promise<boolean> {
    try {
      await connectGmail(payload);
      await refreshMailbox();
      toast.success(t("frontend.mailbox.success_connected"));
      return true;
    } catch (err) {
      toast.error(mailboxErrorMessage(err));
      return false;
    }
  }

  // ── OAuth connect ─────────────────────────────────────────
  async function handleOAuthStart() {
    try {
      const { auth_url } = await startGoogleOAuth();
      window.open(auth_url, "_blank", "width=500,height=600");
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
        await refreshMailbox();
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
      await refreshMailbox();
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
          <h2 className="text-base font-medium">
            {t("frontend.mailbox.section_title")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("frontend.mailbox.product_description")}
          </p>
        </div>
        <span title={t("frontend.mailbox.product_tooltip")}>
          <HelpCircle className="size-4 text-muted-foreground" />
        </span>
      </div>

      <MailboxConfiguration
        mailbox={mailbox}
        error={error}
        isDemo={isDemo}
        oauthConnectEnabled={oauthConnectEnabled}
        disconnecting={disconnecting}
        testing={testing}
        onConnect={handleConnectAppPassword}
        onStartOAuth={handleOAuthStart}
        onDisconnect={handleDisconnect}
        onTest={handleTest}
      />
    </div>
  );
}
