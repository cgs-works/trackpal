import { useState } from "react";
import { ArrowLeft, Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestContextualHelp } from "@/features/help/contextual-help";
import { HELP_TARGETS } from "@/features/help/help-targets";
import { t } from "@/i18n";
import type { GmailAppPasswordConnect } from "../services/settings-api";

export interface GmailSetupAssistantProps {
  onConnect(payload: GmailAppPasswordConnect): Promise<boolean>;
}

type Step = "instructions" | "credentials";

function BackButton({ onClick }: { onClick(): void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-3.5" />
      {t("frontend.mailbox.back")}
    </button>
  );
}

interface AppPasswordInstructionsProps {
  privateHelpEnabled: boolean;
  onContinue(): void;
}

function AppPasswordInstructions({
  privateHelpEnabled,
  onContinue,
}: AppPasswordInstructionsProps) {
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
        <Button type="button" onClick={onContinue} className="w-full">
          {t("frontend.mailbox.have_app_password")}
        </Button>
        {privateHelpEnabled && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => requestContextualHelp(HELP_TARGETS.mailbox)}
            className="w-full"
          >
            {t("frontend.mailbox.view_tutorial")}
          </Button>
        )}
      </div>
    </div>
  );
}

interface CredentialsFormProps {
  email: string;
  appPassword: string;
  showPassword: boolean;
  submitting: boolean;
  onEmailChange(value: string): void;
  onAppPasswordChange(value: string): void;
  onShowPasswordChange(visible: boolean): void;
  onBack(): void;
  onSubmit(event: React.FormEvent): Promise<void>;
}

function CredentialsForm({
  email,
  appPassword,
  showPassword,
  submitting,
  onEmailChange,
  onAppPasswordChange,
  onShowPasswordChange,
  onBack,
  onSubmit,
}: CredentialsFormProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <BackButton onClick={onBack} />

      <div className="space-y-2">
        <Label htmlFor="gmail-email">{t("frontend.mailbox.google_email")}</Label>
        <Input
          id="gmail-email"
          type="email"
          required
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
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
            onChange={(event) => onAppPasswordChange(event.target.value)}
            autoComplete="new-password"
          />
          <button
            type="button"
            onClick={() => onShowPasswordChange(!showPassword)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label={
              showPassword
                ? t("frontend.mailbox.hide_password")
                : t("frontend.mailbox.show_password")
            }
          >
            {showPassword ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("frontend.mailbox.app_password_field_help")}
        </p>
      </div>

      <Button type="submit" disabled={submitting} className="w-full">
        {submitting && <Loader2 className="size-4 mr-1 animate-spin" />}
        {submitting
          ? t("frontend.mailbox.connecting")
          : t("frontend.mailbox.connect_gmail")}
      </Button>
    </form>
  );
}

export function GmailSetupAssistant({ onConnect }: GmailSetupAssistantProps) {
  const [step, setStep] = useState<Step>("instructions");
  const [email, setEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const privateHelpEnabled =
    import.meta.env.VITE_PRIVATE_HELP_ENABLED !== "false";

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const connected = await onConnect({
        mailbox_email: email,
        app_password: appPassword,
      });
      if (!connected) {
        setAppPassword("");
      }
    } finally {
      setSubmitting(false);
    }
  }

  switch (step) {
    case "instructions":
      return (
        <AppPasswordInstructions
          privateHelpEnabled={privateHelpEnabled}
          onContinue={() => setStep("credentials")}
        />
      );
    case "credentials":
      return (
        <CredentialsForm
          email={email}
          appPassword={appPassword}
          showPassword={showPassword}
          submitting={submitting}
          onEmailChange={setEmail}
          onAppPasswordChange={setAppPassword}
          onShowPasswordChange={setShowPassword}
          onBack={() => setStep("instructions")}
          onSubmit={handleSubmit}
        />
      );
  }
}
