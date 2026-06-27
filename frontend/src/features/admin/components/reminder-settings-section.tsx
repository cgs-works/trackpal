import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertCircle, Plus, X } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getLocale, t } from "@/i18n";
import { useSettingsStore } from "@/store/settings";

const PREVIEW_PLACEHOLDERS = {
  client_name: "María Pérez",
  service_name: "Netflix",
  days: "3",
  streaming_email: "cliente@example.com",
  expires_at: "2026-07-01",
};

const DEFAULT_MESSAGES = {
  en: {
    tenant: "Reminder: {{client_name}}'s {{service_name}} subscription expires in {{days}} days.",
    client: "Your {{service_name}} subscription expires in {{days}} days.",
  },
  es: {
    tenant: "Recordatorio: la suscripción de {{client_name}} a {{service_name}} vence en {{days}} días.",
    client: "Tu suscripción de {{service_name}} vence en {{days}} días.",
  },
};

type ApiErrorDetail = string | Array<{ msg?: string }>;

function getDefaultMessages(locale: string) {
  return DEFAULT_MESSAGES[locale as "en" | "es"] || DEFAULT_MESSAGES.en;
}

function getReminderSettingsError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: ApiErrorDetail } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) return detail.map((item) => item.msg || "Unknown error").join("; ");
  return error instanceof Error ? error.message : t("frontend.subscriptions.error_reminder_settings");
}

function renderPreview(template: string): string {
  let result = template;
  for (const [key, value] of Object.entries(PREVIEW_PLACEHOLDERS)) {
    result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), value);
  }
  return result;
}

export function ReminderSettingsSection() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [locale, setLocale] = useState(getLocale());
  const defaults = getDefaultMessages(locale);
  const {
    reminderSettings,
    tenantSettings,
    reminderSettingsLoaded,
    loadReminderSettings,
    loadTenantSettings,
    updateReminderSettings,
  } = useSettingsStore();
  const [settings, setSettings] = useState({
    reminders_enabled: false,
    warning_days: [7, 3, 1] as number[],
    reminder_time: "09:00",
    recipient_mode: "tenant_only" as "tenant_only" | "client_only" | "both",
    custom_message_tenant: null as string | null,
    custom_message_client: null as string | null,
  });
  const [customDay, setCustomDay] = useState("");
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const loadData = useCallback(async () => {
    setError("");
    setIsLoading(true);
    setLocale(getLocale());
    try {
      await Promise.all([loadReminderSettings(), loadTenantSettings()]);
    } catch (err: unknown) {
      setError(getReminderSettingsError(err));
    } finally {
      setIsLoading(false);
    }
  }, [loadReminderSettings, loadTenantSettings]);

  useEffect(() => {
    if (reminderSettingsLoaded && reminderSettings) {
      setSettings({
        reminders_enabled: reminderSettings.reminders_enabled,
        warning_days: reminderSettings.warning_days || [7, 3, 1],
        reminder_time: reminderSettings.reminder_time || "09:00",
        recipient_mode: reminderSettings.recipient_mode || "tenant_only",
        custom_message_tenant: reminderSettings.custom_message_tenant,
        custom_message_client: reminderSettings.custom_message_client,
      });
    }
  }, [reminderSettingsLoaded, reminderSettings]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const validate = useCallback(() => {
    const errors: Record<string, string> = {};
    if (settings.reminders_enabled) {
      if (settings.warning_days.length === 0) errors.warning_days = t("frontend.subscriptions.error_warning_days_required");
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(settings.reminder_time)) {
        errors.reminder_time = t("frontend.subscriptions.error_invalid_time");
      }
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [settings]);

  useEffect(() => {
    validate();
  }, [settings, validate]);

  function toggleWarningDay(day: number) {
    setSettings((prev) => {
      const days = prev.warning_days.includes(day)
        ? prev.warning_days.filter((d) => d !== day)
        : [...prev.warning_days, day].sort((a, b) => a - b);
      return { ...prev, warning_days: days };
    });
  }

  function addCustomDay() {
    const day = parseInt(customDay, 10);
    if (!Number.isNaN(day) && day > 0 && !settings.warning_days.includes(day)) {
      setSettings((prev) => ({ ...prev, warning_days: [...prev.warning_days, day].sort((a, b) => a - b) }));
      setCustomDay("");
    }
  }

  function removeWarningDay(day: number) {
    setSettings((prev) => ({ ...prev, warning_days: prev.warning_days.filter((d) => d !== day) }));
  }

  async function handleSave() {
    if (!validate()) return;
    setIsSaving(true);
    setError("");
    try {
      await updateReminderSettings(settings);
      toast.success(t("frontend.subscriptions.reminder_saved"));
    } catch (err: unknown) {
      setError(getReminderSettingsError(err));
    } finally {
      setIsSaving(false);
    }
  }

  const hasWarningDaysError = settings.reminders_enabled && Boolean(validationErrors.warning_days);
  const hasTimeError = settings.reminders_enabled && Boolean(validationErrors.reminder_time);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-7">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </Alert>
      )}

      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <Label className="text-base font-medium">{t("frontend.subscriptions.reminders_enabled")}</Label>
          <p className="text-sm text-muted-foreground">{t("frontend.subscriptions.reminders_desc")}</p>
        </div>
        <Switch checked={settings.reminders_enabled} onCheckedChange={(checked) => setSettings((prev) => ({ ...prev, reminders_enabled: checked }))} />
      </div>

      {settings.reminders_enabled && (
        <>
          <Separator />
          <div className="flex flex-col gap-2.5">
            <Label className="text-sm font-medium">{t("frontend.subscriptions.timezone")}</Label>
            <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
              {t("frontend.subscriptions.reminder_time_help")} {tenantSettings?.timezone || "UTC"}
            </div>
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className={hasWarningDaysError ? "text-sm font-medium text-destructive" : "text-sm font-medium"}>
              {t("frontend.subscriptions.warning_days")}
            </Label>
            <div className="flex flex-wrap items-center gap-2">
              {[7, 3, 1].map((day) => (
                <label key={day} className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 transition-colors hover:bg-accent">
                  <input type="checkbox" checked={settings.warning_days.includes(day)} onChange={() => toggleWarningDay(day)} className="rounded" />
                  <span className="text-sm">{day} {day === 1 ? t("frontend.subscriptions.day") : t("frontend.subscriptions.days")}</span>
                </label>
              ))}
              <div className="flex items-center gap-1.5">
                <Input type="number" min={1} value={customDay} onChange={(e) => setCustomDay(e.target.value)} placeholder={t("frontend.subscriptions.placeholder_custom")} className="h-9 w-20 text-sm" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomDay(); } }} />
                <Button type="button" variant="outline" size="icon" className="h-9 w-9 shrink-0" onClick={addCustomDay} disabled={!customDay}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
            {settings.warning_days.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {settings.warning_days.map((day) => (
                  <span key={day} className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
                    {day} {day === 1 ? t("frontend.subscriptions.day") : t("frontend.subscriptions.days")}
                    <button type="button" onClick={() => removeWarningDay(day)} aria-label={t("frontend.subscriptions.remove_day", { day: String(day) })} className="transition-colors hover:text-destructive">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {hasWarningDaysError && <p className="text-xs text-destructive">{validationErrors.warning_days}</p>}
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className={hasTimeError ? "text-sm font-medium text-destructive" : "text-sm font-medium"}>{t("frontend.subscriptions.reminder_time")}</Label>
            <p className="text-sm text-muted-foreground">{t("frontend.subscriptions.reminder_time_help")}</p>
            <Input type="time" value={settings.reminder_time} onChange={(e) => setSettings((prev) => ({ ...prev, reminder_time: e.target.value }))} className={hasTimeError ? "w-40 border-destructive" : "w-40"} />
            {hasTimeError && <p className="text-xs text-destructive">{validationErrors.reminder_time}</p>}
          </div>

          <div className="flex flex-col gap-2.5">
            <Label className="text-sm font-medium">{t("frontend.subscriptions.recipients")}</Label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                { value: "tenant_only", label: t("frontend.subscriptions.recipient_mode_tenant_only"), desc: t("frontend.subscriptions.recipient_desc_tenant_only") },
                { value: "client_only", label: t("frontend.subscriptions.recipient_mode_client_only"), desc: t("frontend.subscriptions.recipient_desc_client_only") },
                { value: "both", label: t("frontend.subscriptions.recipient_mode_both"), desc: t("frontend.subscriptions.recipient_desc_both") },
              ].map((opt) => (
                <label key={opt.value} className={settings.recipient_mode === opt.value ? "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-primary bg-primary/5 p-3 transition-colors" : "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-border p-3 transition-colors hover:bg-accent"}>
                  <input type="radio" name="recipient_mode" value={opt.value} checked={settings.recipient_mode === opt.value} onChange={(e) => setSettings((prev) => ({ ...prev, recipient_mode: e.target.value as "tenant_only" | "client_only" | "both" }))} className="sr-only" />
                  <span className="text-sm font-medium">{opt.desc}</span>
                  <span className="text-center text-xs text-muted-foreground">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          <Separator />
          <div className="flex flex-col gap-4">
            <div>
              <Label className="text-sm font-medium">{t("frontend.subscriptions.custom_messages")}</Label>
              <p className="mt-1 text-sm text-muted-foreground">
                {t("frontend.subscriptions.custom_messages_hint", { placeholder: "{{placeholder}}" })}
              </p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label>{t("frontend.subscriptions.custom_message_tenant")}</Label>
                <textarea className="min-h-28 rounded-md border bg-background p-3 text-sm" value={settings.custom_message_tenant ?? defaults.tenant} onChange={(e) => setSettings((prev) => ({ ...prev, custom_message_tenant: e.target.value || null }))} />
                <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{renderPreview(settings.custom_message_tenant ?? defaults.tenant)}</p>
              </div>
              <div className="flex flex-col gap-2">
                <Label>{t("frontend.subscriptions.custom_message_client")}</Label>
                <textarea className="min-h-28 rounded-md border bg-background p-3 text-sm" value={settings.custom_message_client ?? defaults.client} onChange={(e) => setSettings((prev) => ({ ...prev, custom_message_client: e.target.value || null }))} />
                <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{renderPreview(settings.custom_message_client ?? defaults.client)}</p>
              </div>
            </div>
          </div>
        </>
      )}

      <Button type="button" className="self-start" onClick={() => void handleSave()} disabled={isSaving || Object.keys(validationErrors).length > 0}>
        {isSaving ? t("frontend.common.saving") : t("frontend.common.save")}
      </Button>
    </div>
  );
}
