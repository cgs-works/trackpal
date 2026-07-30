import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, Eye, EyeOff, Loader2 } from "lucide-react";
import { t } from "@/i18n";
import { requestContextualHelp } from "@/features/help/contextual-help";
import { HELP_TARGETS } from "@/features/help/help-targets";

export interface GmailAppPasswordConnect {
  mailbox_email: string;
  app_password: string;
}

export interface GmailSetupAssistantProps {
  oauthConnectEnabled: boolean;
  onConnect(payload: GmailAppPasswordConnect): Promise<boolean>;
  onStartOAuth(): Promise<void>;
}

type Step = "instructions" | "credentials";

export function GmailSetupAssistant({
  oauthConnectEnabled,
  onConnect,
  onStartOAuth,
}: GmailSetupAssistantProps) {
  const [step, setStep] = useState<Step>("instructions");
  const [email, setEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const privateHelpEnabled =
    import.meta.env.VITE_PRIVATE_HELP_ENABLED !== "false";

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);
      try {
        const ok = await onConnect({
          mailbox_email: email,
          app_password: appPassword,
        });
        if (!ok) {
          setAppPassword("");
        }
      } finally {
        setSubmitting(false);
      }
    },
    [email, appPassword, onConnect],
  );

  function handleViewTutorial() {
    requestContextualHelp(HELP_TARGETS.mailbox);
  }

  if (step === "instructions") {
    return (
      <div className="space-y-4">
        <div className="space-y-2">
          <h3 className="text-sm font-medium">
            {t("frontend.mailbox.app_password_step_title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("frontend.mailbox.app_password_step_description")}
          </p>
        </div>

        <a
          href="https://myaccount.google.com/apppasswords"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {t("frontend.mailbox.open_google")}
        </a>

        <p className="text-sm text-muted-foreground">
          {t("frontend.mailbox.app_password_step_help")}
        </p>

        <div className="flex flex-col gap-2">
          <Button
            type="button"
            onClick={() => setStep("credentials")}
            className="w-full"
          >
            {t("frontend.mailbox.have_app_password")}
          </Button>
          {privateHelpEnabled && (
            <Button
              type="button"
              variant="ghost"
              onClick={handleViewTutorial}
              className="w-full"
            >
              {t("frontend.mailbox.view_tutorial")}
            </Button>
          )}
        </div>
      </div>
    );
  }

  // credentials step
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <button
        type="button"
        onClick={() => setStep("instructions")}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        {t("frontend.mailbox.back")}
      </button>

      <div className="space-y-2">
        <Label htmlFor="gmail-email">{t("frontend.mailbox.google_email")}</Label>
        <Input
          id="gmail-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="gmail-app-password">
          {t("frontend.mailbox.app_password")}
        </Label>
        <div className="relative">
          <Input
            id="gmail-app-password"
            type={showPassword ? "text" : "password"}
            required
            value={appPassword}
            onChange={(e) => setAppPassword(e.target.value)}
            autoComplete="new-password"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label={showPassword ? t("frontend.mailbox.hide_password") : t("frontend.mailbox.show_password")}
          >
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("frontend.mailbox.app_password_field_help")}
        </p>
      </div>

      <Button type="submit" disabled={submitting} className="w-full">
        {submitting ? (
          <Loader2 className="size-4 mr-1 animate-spin" />
        ) : null}
        {submitting
          ? t("frontend.mailbox.connecting")
          : t("frontend.mailbox.connect_gmail")}
      </Button>
    </form>
  );
}
